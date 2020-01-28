import argparse
from datetime import datetime
import math

from dotenv import load_dotenv
load_dotenv()
import pandas as pd
import randorank as rr
import sqlalchemy as sa

from db import connect_races, connect_rankings

def parse_arguments():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='commands', action='store')

    parser_filter = subparsers.add_parser('filter_players')
    parser_filter.add_argument('players',
                               type=str,
                               help='A space or comma separated string of players not to rank')
    parser_filter.set_defaults(func=filter_players)

    parser_rank = subparsers.add_parser('rank')
    parser_rank.set_defaults(func=rank)
    # I had an "export" argument here that could take the final results and
    # pipe them to stdout as json or what have you, but we could just read from
    # the database if/when necessary I figure.

    parser_configure = subparsers.add_parser('configure')
    parser_configure.set_defaults(func=configure)
    parser_configure.add_argument('--period_length',
                                  type=int,
                                  required=True,
                                  help='Length of a period in weeks',
                                  default=4)
    parser_configure.add_argument('--num_periods',
                                  type=int,
                                  required=True,
                                  help='Number of periods in a season',
                                  default=3)
    parser_configure.add_argument('--season_start',
                                  type=str,
                                  required=True,
                                  help='''
                                       The date you want the season to start in the
                                       format YYYY-MM-DD
                                       ''')

    parser.parse_args()

def rank(args):
    '''
    Gets all season race data from races db based on season start date in "meta" table
    of rankings db. Filters and separates races by category. Updates rankings db with
    current rankings, where that data can be used as desired. Each category should
    have its own table in the rankings database.
    '''
    # first get the configuration data from the rankings db
    rankings_conn = connect_races()
    rankings_cursor = rankings_conn.cursor()
    if rankings_conn.execute("SELECT * FROM meta").fetchone() is None:
        print("Please set config values with the config command")
        return
    period_length = rankings_cursor.execute("SELECT period_length FROM meta").fetchone()
    num_periods = rankings_cursor.execute("SELECT num_periods FROM meta").fetchone()
    season_start = rankings_cursor.execute("SELECT season_start FROM meta").fetchone()
    season_end = season_start + datetime.timedelta(weeks=num_periods * period_length)
    filtered_players = rankings_cursor.execute("SELECT players FROM filtered_players").fetchall()

    # get all the races in the season. we sort ascending here for the function that separates
    # races into periods.
    races_conn = connect_races()
    races_cursor = races_conn.cursor()
    race_query = f'SELECT * FROM races WHERE (date >= {season_start} AND date < {season_end}) ORDER BY date ASC'
    
    # after fetching the previous query which gets all the races, we have
    # tuples with race ids and goals. we separate the ids by goal and then
    # use the ids for those goals to get those races

    # [(id, 'alttphacks', goal, datetime, num_racers)]
    race_ids = races_cursor.execute(race_query).fetchall()
    open_standard_ids = filter(lambda x: x[2] in open_standard_goals, race_ids)
    cross_keys_ids = filter(lambda x: x[2] in cross_keys_goals, race_ids)
    mystery_ids = filter(lambda x: x[2] in mystery_goals, race_ids)

    open_standard_races = get_races(open_standard_ids, races_cursor, filtered_players)
    cross_keys_races = get_races(cross_keys_ids, races_cursor, filtered_players)
    mystery_races = get_races(mystery_ids, races_cursor, filtered_players)

    # now we separate all the races that we got earlier for the whole season into periods
    # which are calculated at the same time as if they happened at once. with glicko-2,
    # it doesn't matter *when* a game happened within a period, only that it happened
    # during that period
    season_open_standard = separate_periods(open_standard_races, season_start, period_length)
    season_cross_keys = separate_periods(open_standard_races, season_start, period_length)
    season_mystery = separate_periods(open_standard_races, season_start, period_length)

    # we have all our races separated into periods, now we can rank and update each
    # category's db table

    # we'll use the same constants for every category; they should be roughly accurate
    # but it may be worth looking into tweaking some of these for cross keys and mystery
    glicko_constants = {'tau': .2,
                        'multi_slope': .008,
                        'multi_cutoff': 6,
                        'norm_factor': 1.3,
                        'victory_margin': 600,
                        'initial_rating': 1500,
                        'initial_deviation': 300,
                        'initial_volatility': .23
                       }
    open_standard_rankings = []
    cross_keys_rankings = []
    mystery_rankings = []

    # loop through every category's races and get the final rankings to put in 
    # above lists[-1]
    for period in season_open_standard:
        if len(open_standard_rankings) == 0:
            # we're on the first period
            new_period = rr.MultiPeriod()
            new_period.set_constants(glicko_constants)
        else:
            new_period = rr.MultiPeriod()
            new_period.set_constants(glicko_constants)
            # if we're not calculating the first period, we add player variables
            # from the previous period
            new_period.add_players(open_standard_rankings[-1])
        # first we filter the period's races to exclude races with only one participant
        # (just in case)
        filtered_period = filter(lambda x: len(x) > 1, period)                                          
        # now we do another filter to make sure that there's at least one finisher and that
        # everybody didn't forfeit
        filtered_period = filter(lambda x: len(list(filter(lambda y: math.isnan(y) is False, x.values()))) >= 1, period)
        # now we can add the filtered period as a list (since it is currently a filter object)
        new_period.add_races(list(filtered_period))
        
        # put the final rankings for this period into a dict, add that dict to the end of
        # the rankings list we made earlier so we can reference it later. glicko-2 uses
        # rating, deviation, and volatility from the previous period in its calculations
        # for subsequent periods (we add these with the add_players method above in the 
        # else branch where we're not on the first period)
        mid_rankings = new_period.rank()
        open_standard_rankings.append(mid_rankings)

    for period in season_cross_keys:
        if len(cross_keys_rankings) == 0:
            new_period = rr.MultiPeriod()
            new_period.set_constants(glicko_constants)
        else:
            new_period = rr.MultiPeriod()
            new_period.set_constants(glicko_constants)
            new_period.add_players(cross_keys_rankings[-1])

        filtered_period = filter(lambda x: len(x) > 1, period)                                          
        filtered_period = filter(lambda x: len(list(filter(lambda y: math.isnan(y) is False, x.values()))) >= 1, period)
        new_period.add_races(list(filtered_period))
        
        mid_rankings = new_period.rank()
        cross_keys_rankings.append(mid_rankings)
    
    for period in season_mystery:
        if len(mystery_rankings) == 0:
            new_period = rr.MultiPeriod()
            new_period.set_constants(glicko_constants)
        else:
            new_period = rr.MultiPeriod()
            new_period.set_constants(glicko_constants)
            new_period.add_players(mystery_rankings[-1])
        
        filtered_period = filter(lambda x: len(x) > 1, period)                                          
        filtered_period = filter(lambda x: len(list(filter(lambda y: math.isnan(y) is False, x.values()))) >= 1, period)
        new_period.add_races(list(filtered_period))

        mid_rankings = new_period.rank()
        mystery_rankings.append(mid_rankings)

   # now we have the most current rankings for each category in the last element of
   # their ranking list above, in the form {'name': {'system variable': variable value}}
   # we can use the data in these dicts for whatever purpose (eg displaying on a leaderboard)

def configure(args):
    '''
    Accepts the configuration parameters and adds them to a single-row "meta" table
    in the database.
    '''
    period_length = int(args.period_length)
    num_periods = int(args.num_periods)
    season_start = datetime.strptime(f'{args.season_start} 00:00:00', "%Y-%M-%d %H:%M:%S")

    config_query = f'''
                   REPLACE INTO meta (period_length, num_periods, season_start)
                   VALUES ({period_length},{num_periods},{season_start})
                   '''

    conn = connect_rankings()
    cursor = conn.cursor()
    cursor.execute(config_query)
    conn.commit()

    conn.close()

def filter_players(args):
    '''
    Accepts a comma or space separated string of players you don't want to rank
    and adds them into a single column table in the db.
    '''
    added_players = [(f'{i},') for i in args.players.split(" ,")]
    
    conn = connect_rankings()
    cursor = conn.cursor()
    cursor.executemany(f'INSERT INTO filtered_players VALUES {added_players}')
    conn.commit()

    conn.close()

def get_races(race_ids, filtered_players, cursor):
    all_races = []
    for race_id in race_ids:
        race_query = f'SELECT * FROM results WHERE race_id={race_id}'                                   
        date_query = f'SELECT date FROM races where id={race_id}'
        cursor.execute(race_query)
        race = cursor.fetchall()
        race = map(lambda x: (x[3], x[4]), race)
        race = dict(filter(lambda x: x[0] not in filtered_players, race))                                     
        race = {k: math.nan if v is None else v for k, v in race.items()}

        cursor.execute(date_query)
        date = cursor.fetchone()[0]

        race = (race, date)
        all_races.append(race)
    
    return all_races

def separate_periods(races, season_start, period_length):
    """
    Divides races into periods of four weeks each
    """
    period_delta = datetime.timedelta(weeks=period_length)
    period_lower = season_start
    period_upper = season_start + period_delta
    period_buf = []
    bucket = []
    for race in races:
        # the date part of the race tuples is a python datetime object
        # so isocalendar()[1] is the week in the year (1-52) that the race
        # occurred.

        # this algorithm (hard coded for 2 week periods) will iteratively
        # add races into a "bucket" then once it reaches a race (in the
        # collection of tuples that we sorted earlier) in the next period,
        # the bucket has all of a period's races. it adds that full bucket
        # to period_buf, puts the race (which occurred in the next period)
        # to a new bucket, and starts over
        if period_lower <= race[1] < period_upper:
            bucket.append(race[0])
        else:
            period_buf.append(bucket)
            period_lower += period_delta
            period_upper += period_delta
            bucket = []
            bucket.append(race[0])

    # add the last bucket
    period_buf.append(bucket)

    return period_buf

def main():
    args = parse_arguments()

# these are SRL goals used to filter the different categories
# could configure Sahasrahbot to set certain goals and put them here
# note: races without these exact goals will not be ranked
# could also use regular expressions here and in the rank command
# function to filter by keywords/phrases instead of entire goal string
# if we want to include more races, such as tourney matches

# no inverted or keysanity, maybe keysanity in its own leaderboard?
open_standard_goals = [
        'vt8 randomizer - casual open',
        'vt8 randomizer - standard',
        'vt8 randomizer - casual',
        'vt8 randomizer - open w/ boots start',
        'vt8 randomizer - fast ganon open w/ boots start',
        'vt8 randomizer - ambrosia'
        ]
cross_keys_goals = ['vt8 randomizer - normal open keysanity + entrance shuffle']
mystery_goals = [
        'vt8 randomizer - mystery pogchampion',
        'vt8 randomizer - mystery weighted',
        'vt8 randomizer - mystery unweighted',
        'vt8 randomizer - mystery friendly'
        ]
# need to figure out how the glitched community wants to do this
glitched_goals = []
