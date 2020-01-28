# Overview

This is a template/example script that could be used to rank z3r races with
the [RandoRank python library](https://github.com/cassidoxa/RandoRank)'s 
multiplayer Glicko-2 implementation. It requires some configuration and
currently uses two databases, one which it draws race data from and which
is identical to Synack's SRL database, and another which stores rankings
and ranking-related config info. Currently these can be configured in the 
`db.py` module. 

The script assumes that the ranking database has roughly the following
tables and schema: a one column "filtered\_runners" table that contains
runners we don't want to rank as rows, a "meta" table that stores a row with
three values: period\_length (in weeks), num\_periods, the number of periods in
a season, and season\_start which is the date that the season being ranked
starts (the script determines all other dates it uses based on this.)

# Glicko-2 and RandoRank

The Glicko-2 ranking system works by assigning players 3 values: a rating,
a deviation, and a volatility. There are some additional values that must
be set for stock glicko as well as some values that the multiplayer
implementation uses uniquely. These are explained further in the RandoRank
readme and the original Glicko-2 document linked in that readme.

The first time someone plays a ranked game, they're assigned a set of default
values. A period length is determined beforehand as well. Glicko-2 considers
all games in a period to have happened simultaneously, and at the end of a
period, the rating, deviation, and volatility are calculated and fed into
the next period. Players can race in subsequent periods without having raced in
the first, and will still be assigned default values and ranked normally. A 
"season" is not a concept defined by Glicko-2 but rather something we will use
in our own implementation. This script has my recommended system constants as
well as period and season length, but feel free to adjust.

# Commands

This script is designed as an executable that can be configured per-season and
run at regular intervals to get race data from the races database and transform
it into current rankings. You can use the following commands:

## configure

This sets some period date values in the rankings database so the script knows
which races to pull from the races database and how to separate them into periods.
It accept three required arguments. Ex:

`z3ranker configure --period_length 4 --num_periods 3 --season_start YYYY-MM-DD`

As written, a year will not be evenly divided into periods. Here, a
season will consist of three periods and 12 weeks. This only accounts for 48
weeks out of the year. But the script could be refactored to use months instead
of weeks if desired. Also, this command will overwrite the current row in the
database whenever it's run. 

## filter

This command accepts an argument in quotes. The argument should be the name of the
runner or runners (separated by space or comma) as in the races database.

## rank

This command accepts no arguments. It takes all the data from the period at
once, separates into categories based on SRL goal, calculates the whole season
based on races currently in the races database, and produces a dictionary with
names as keys and a dict containing that player's rating variables Suppose I
wanted to get Veetorp's rating and deviation after ranking, I would do it
like so:
```python
veetorp_rating = rankings_dict['Veetorp']['rating']
veetorp_deviation = rankings_dict['Veetorp']['deviation']
```

As written, the script does nothing with these values. Ideally they should be
stored in a database table for each category such that the most recent
rankings can be easily fetched for display on a leaderboard or whatever
purpose.
