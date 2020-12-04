# Python Scripts for scraping the AGU2020 meeting website
Perhaps, like me, you are a Geosciences department web developer and you want to put up a schedule of your department member's AGU talks on your website, to make it easier for everyone to find out who is talking when.

I wrote this Python 3.x script to do just that.  The script and Jupyter notebook are included above.

The script relies on a csv file containing a list of people in your department that is formatted a certain way. However, if you're handy with Python you can alter the script to input whatever file you wish.  The code for parsing that file starts on line 31.

The script is written for the Geosciences department U-Mass Amherst, but if you know Python you can change out your institution in the elif statement in line 152 (apologies for not parameterizing that, I'm still a newbie).
