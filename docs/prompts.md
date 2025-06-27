# 1. https://chatgpt.com/codex/tasks/task_e_685dfaaa7734832cb1fbd6cafb3e0419 
I would like to analyze my sleep data.

This is a fairly empty repo.

You'll be reading from my semi-structured sleep logs txt file, parsing that into a pandas dataframe, then saving that to `output/data.tsv`.

Then, you should create an `output/stats-WEEK_LABEL.tsv` for each week:
- Total alcoholic drinks for the week
- Average values
  - most importantly: bed_time, wake_up_time, wind_down_start_time, get_out_of_bed_time
- Average offset
  - This is the amount of time that deviates from the expected time for the given metric. For now stick with these times:
 - Any other metrics you can think of are welcome.

Here are the questions you'll find in the log that apply to each of these 4 metrics I just mentioned:
- wind_down_start_time: "1b. What time start winding down?"
- bed_time: "1.2b. What time did you get into bed & commit to sleep?"
- wake_up_time: "6. What time did you wake up?"
- get_out_of_bed_time: "7. What time did you get out of bed?"

Then, create an `output/stats.tsv` which for now will just be averages of all the values in the individual `output/stats-WEEK_LABEL.tsv` files.

Inputs:
input/log.txt

It will look like this:
(by week)
    Fri4/25-Wed4/30
        ...
    Thu6/19-Wed25
        ...

The actual "(by week)" part is unimportant. you can ignore that. You should be looking at the indented blocks that look like this "Fri4/25-Wed4/30". These will be "1 indent" in, which will either be 1 tab or 4 spaces. These are MONTH/DAY labels. You can ignore the "day of the week", e.g. "Fri" or "Wed" parts of it. You should also interpret all of these as being from the year 2025, or you can just forget about the year part.

Now, within each of these "week blocks", are questions + data that are indented eithe 2 tabs or 8 spaces deep. They'll look like this:

```
	Thu6/19-Wed25
	    1b. What time start winding down? 2:20am 2:50am 2:10am 2:10am 2:20am 3:20am 3:40am
	    1.2b. What time did you get into bed & commit to sleep? 3:34am 4:22am 3:33am 4:13am 4:02am 4:25am 4:25am
	    1.3b. Wind-down activities (if not reading book)
	        Day 1, Jun19: Relaxing viewing, relaxing game
	        Day 2: relaxing game
	        Day 3: relaxing game
	    2. How long do you estimate it took to fall asleep (minutes)? 25 50 12 25 15 35 13
	        Day2, Jun20: Strange GERD episode; 2nd time this has ever happened. Meds did nothing. Was sitting up straight. No food for 4-5 hours. No spicy. 1 drink 8 hours prior.
	    ...
	    3. How many times did you wake up during the night? 0 0 0 0 1 0 0
	        (Not counting your final wake up for the day)
	    4. In total, how long did these awakenings last (minutes)? . . . . 1 . .
	    5. When awake during the night, how long did you spend out of bed (minutes)? . . . . . . .
	    ...
	    6. What time did you wake up? 11:30am 11:30am 11:30am 11:30am 11:30am 11:30am 11:30am
	        (Final wake up of morning)
	    7. What time did you get out of bed? 11:45am 12:35pm 11:40am 12:01pm 11:43am 11:57am 11:40am
	        Day 2, Jun20: Probably will need to switch to physical alarms. Ashley is helpful, but on some days like today, I was extraordinarily tired. I don't know why. She didn't stay for more than a second though, and didn't turn on the light until later. The worst thing was probably letting in my cat, which slipped under the covers to sleep against me, which is just about impossible for me to resist.
	    8. In TOTAL, how many hours of sleep did you get? 7:31 6:18 7:45 6:52 7:12 6:30 6:52
	    9. In TOTAL, how many hours did you spend in bed? 8:11 8:13 8:07 7:48 7:41 7:32 7:15
	    ...
	    10. Quality of your sleep (1-10)? 10 10 10 10 9 10 10
	    11. Did you take naps during the day? 0 0 0 0 0 0 0
	    12. Mood during the day (1-10)? 9 6 7 7 8.5 7 9
	    13. Fatigue level during the day (1-10)? 0 5 3.5 3 2 3 1
	    ...
	    14. If alcohol, how many standard drinks? 0 1.3 0 2 3 0 0
	    15. - what type? . beer5%16oz . beer5.6%12oz|beer4.6%12oz mixed5%12oz|mixed5%12oz|beer5%12oz . .
	    16. - what time? . 7:30am . 12:40am|1:18am 10:30pm|11:42pm|12:50pm 
	    17. Second wind? . . . 5pm . 10:30pm .
	        Day 4, Jun22: Normally I think of "second wind" as something that happens late at night, but I realize that there is a sense in which this can happen multiple times a day. For example, today, I was very tired from when I woke up, until almost 5pm (5.5 hours after waking up). But then it started to get better. This decrease in sleepiness lasted mostly right up until bed time. I should one that up until and for 1 hour after 5pm, I had a fair amount of caffeine (later than I typically do), but also engaged in hours of active, cognitively demanding work with little break. Maybe that is the cause.
	        Day 6, June 24th: strange I seem to have kind of multiple second winds. I had much more energy than usual when I woke up, but I crashed a few hours later. Usually it's the opposite. And then a few hours after that I had a second wind. Then my cats started to snuggle with me and I got tired again. Then I had a second wind at 11:00 p.m. again.
```

There are some dividers "...". Ignore those lines.

If you see a ".", this indicates an NA value. You can also interpet these as 0's.

If you don't understand how to parse some questions + data rows, such as "15. - what type? . beer5%16oz . beer5.6%12oz|beer4.6%12oz mixed5%12oz|mixed5%12oz|beer5%12oz . .", simply ignore them.

Let's take a look at one of the questions:
```
	    7. What time did you get out of bed? 11:45am 12:35pm 11:40am 12:01pm 11:43am 11:57am 11:40am
	        Day 2, Jun20: Probably will need to switch to physical alarms. Ashley is helpful, but on some days like today, I was extraordinarily tired. I don't know why. She didn't stay for more than a second though, and didn't turn on the light until later. The worst thing was probably letting in my cat, which slipped under the covers to sleep against me, which is just about impossible for me to resist.
```
Ignore everything that is between the questions, which will be indented further. THese are just notes.

You'll want to separate out the questions, e.g. in this case "7. What time did you get out of bed?", from the data, e.g. "11:45am 12:35pm 11:40am 12:01pm 11:43am 11:57am 11:40am".

These values are space-delimited. 1 value per day.

That should be all you need to know to get started! Good luck.

------------------------------------------------------------------------------------------------------------------------

# 2. n/a
