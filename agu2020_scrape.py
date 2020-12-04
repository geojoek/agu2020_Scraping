# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
# Python script to scrape AGU 2020 presenter list
# Joe Kopera, Dept. of Geosciences, U-Mass Amherst
# November 2020

# NOTE: using lxml library with xpaths here to parse out the html as it is orders of magnitude faster & uses less resources than other parsers

# importing libraries
import os
import re
import requests
import time
from datetime import datetime
from lxml import html
from lxml import etree
print("libraries loaded")

# Parameters
deptListFile = r""
outputScheduleHTML = r""
aguAllAuthorsURL = r"https://agu.confex.com/agu/fm20/webprogram/allauthors.html"

# %% [markdown]
# The following section reads a CSV file of all people in the department and parse that into a list you can use.
#
# The CSV file I use has a specific structure: fullname, firstname, first initial, lastname and that's what the following block of code parses. The file has no fieldnames on the first line.
# I could use CSVDictReader to parse the file but it would take more lines of code to deal with the resulting dictionary.  This is "simpler".

# %%
# Little function to read a text file and dump each line into a list
def buildList(list, listFile):
    with open(listFile, "rt") as inputFile:
        for line in inputFile:
            trimmed = line.rstrip("\n") # to get rid of pesky \n character at end oof the file.
            # Important to have blank line at end of file for this reason, otherwise script misses last line of file
            list.append(trimmed)

deptList = []
buildList(deptList, deptListFile)
print("Department list file successfully read and lists built")

deptParsedList = []
for x in deptList:
    nameParse = re.search("(\w+),([\w\s-]+)$", x) # this uses regex to parse each line in CSV to only return the last 2 columns, which are first initial and last name.
    if nameParse: # check to make sure the above parsing was successful and re() search object exists. Otherwise script will throw error
        deptParsedList.append(nameParse.group(2) + ", " + nameParse.group(1) + ".") # this appends lastname, first initial to the list
    else:
        deptParsedList.append("no match")
print("Department name list has been parsed")

# %% [markdown]
# The following block of code uses the requests and the lxml library to download and parse https://agu.confex.com/agu/fm20/webprogram/allauthors.html into an xml / html tree object that can be iterated through to extract the info. we want

# %%
# Retrieving the webpage using the requests module
page = requests.get(aguAllAuthorsURL)
print(page.url + "\nWaiting 15 seconds for full page load")
time.sleep(15) # wait 15 seconds for the page to load: necessary in the thick of the conference when their server is under heavy load

print("Parsing page with lxml")
tree = html.fromstring(page.content) # loads page into object that lxml will deal with via html method
allAuthors = tree.xpath('//div[@class="item"]') # extracts the div elements that contain the author info via their xpath

# %% [markdown]
# The following parses and cleans up the lxml object into a dictionary.
#
# The basic structure of the page we just got is a list of lastname, initials, and URLs to all of the presentations and sessions they're presenting.
#
# We want to create a dictionary from this with the structure {'lastname-initials': [list of URLs]}
# Parsing the page into a dictionary of all the AGU presenters and URLs to their talks

# %%
aguAllAuthorsDict = {} # creates the dictionary that the following for loop will to add to.
for x in allAuthors:
    authorHash = x.xpath('.//div[@class="author"]/text()') # This returns a list object of the name and initials, which is, luckily, wrapped in a <div> with the css class "author"
    authorParse = re.search("(\W*)([\w ,\.]*)(\W*)",authorHash[0]) # This strips a lot of invisible characters out of the text we just extracted.
    author = str(authorParse.group(2)) # the actual author name we want is represented by the 2nd group of the regex search expression above.
    # print(author)
    talks = x.xpath('.//div[@class="papers"]/a[@class="index"]') # scrapes the list of URLs for each author
    talkList = []
    for talk in talks:
        talkURL = talk.get('href')
        talkList.append(r"https://agu.confex.com/agu/fm20/webprogram/" + talkURL) # adds the full URL
    # print(talkList)
    aguAllAuthorsDict[author] = talkList # adds author as the key for each dictionary item in aguAllAuthorsDict and the list of URLs as the value.
print("Successfully parsed all AGU authors into dictionary of LastName, Initials : ['talkURLs']")

# %% [markdown]
# So we have a list of all the people in our department.
# And we have a list of all of the presenters at AGU
# The following code compares the two lists extracts last names and first initials from the AGU list that matches a name in the department list.  It copies the AGU-name-initial and the list of URLs to a new dictionary.
#
# NOTE: Because the AGU list is only last names + first initial, there will be mismatches and interlopers in the resulting dictionary who aren't in the department! We will deal with this further down in the code.
#
# This is *a lot faster* than going through the entire list of AGU authors and parsing each abstract for them to see if it contains "University of Massachuetts" like I do below... that would be tens of thousands of web pages to fetch and parse!

# %%
allAuthorsList = list(aguAllAuthorsDict.keys()) # generates a list of all AGU presenters from the keys in the dictionary created above, since the keys are people's names with initials
deptPresenters = {} # creating the dictionary to copy matches to.
for person in deptParsedList:
    for x in allAuthorsList:
        if person in x:
            deptPresenters[x] = aguAllAuthorsDict[x] # copies key/value pair from above dictionary to new dictionary to containi only department members
        else:
            pass
print("Department members extracted from AGU presenter list.")

# %% [markdown]
# The following block iterates through each key (lastname and first initial) of the dictionary of department presenters created above, and then iterates through each URL in the list that is the value associated with that key.  It uses requests and lxml to download and parse each URL, which is a page with the talk title, authors, time, and abstract. It cleans dumps all of that info. (except the abstract) into two dictionaries that we can use to create some HTML to put up a custom talk schedule on our own site.
#
# All of the if / else loops to verify that the last-name initial pair really represents someone at U-Mass, check if the URL is valid, or if the URL is a link to a session, talk, or poster, then fetches the title, authors, abstract #, and time from their abstract page and dumps it into a dictionary where the abstract URL is the key.
#
# Since each URL / abstract may have more than one presenter in the department, the department presenters names are stored as a list and appended to, so that that particular nested dictionary key / value pair doesn't get overwritten each time the same URL is parsed.  We then have a loop to check if that URL has already been parsed: if so, it skips re-parsing that URL and just adds the person's name associated with that URL as an item in that list object to save processing time and my own sanity with debugging.
#
# This uses requests.Session() to create a single persistant TCP connection open instead of opening a new session with each GET request to the server: it increases performance and carries much lower risk of overwhelming the server.

# %%
print("\n----------\nScraping abstracts for each department presenter\n----------")

abstractByURLDict = {}
with requests.Session() as session:
    for person in deptPresenters.keys():
         # container to dump dept. Presenter names into in case URL is associated with more than 1 person in dept.
        print("\n\n--- Scraping presentations for {}".format(person))
        # Have to declare these variables here so they don't become unbounded due to nested if/else loops below.
        abstractTitle = ""
        abstractAuthors = ""
        abstractTime = ""
        abstractFormat = ""
        for presentationURL in deptPresenters[person]:
            # personList = []
            time.sleep(0.1) # rate limiter to stop requests from overwhelming server
            abstractPage = session.get(presentationURL)
            if abstractPage.status_code != 200: # checks to see if it's a broken URL.  If it is, it skips.
                print("...URL broken, skipping.")
                pass
            else:
                print ("- Parsing {}".format(presentationURL))
                abstractTree = html.fromstring(abstractPage.content)
                unparsedAuthorsStep1 = abstractTree.xpath('//div[@class="paperauthors"]') # grabbing whole element including inner html here because it's easier to parse than tacking /node() on the end of the xpath. /text() and //text() strip all the tags out and I want to keep the markup tags.
                if not unparsedAuthorsStep1: # check to see if authors are actually listed and there is a value to parse. Sometimes there isn't an authors field and script aborts with traceback error, so this avoids that.
                    print("...Abstract has no authors listed, skipping")
                    pass
                else:
                    for elem in unparsedAuthorsStep1: # because xpath returns elements as list objects
                        unparsedAuthorsStep2 = etree.tostring(elem, pretty_print=True, encoding='unicode') # Since the "authors" field has markup tags for superscript, bold, etc..., this uses etree method to get contents of the above xpath with enclosed tags: https://stackoverflow.com/questions/14896302/get-the-inner-html-of-a-element-in-lxml.  Encoding parameter is necessary for it to output as string object
                        if "Session" in presentationURL: # Checks if URL is for a session description. If so, skip.
                            print("...This is a page for a whole session. Not parsing that mess. Skipped.")
                            break
                        elif "University of Massachusetts" not in unparsedAuthorsStep2 and "Amherst" not in unparsedAuthorsStep2: # Checks if any of authors are from U-Mass Amherst.  If not, skip.
                            print("...{} isn't a UMass person. Skipping.".format(person))
                            break
                        try:
                            if abstractByURLDict[presentationURL]: # Checks if this URL has already been added to the dictionary.
                                print("...URL has already been parsed. Adding {} to namefield in dictionary and skipping".format(person))
                                abstractByURLDict[presentationURL]['deptPresenters'].append(person) # if it has, add person this is associated with as a presenter
                                print("...{} are now both listed as presenters for this abstract".format(abstractByURLDict[presentationURL]['deptPresenters']))
                                break
                        except KeyError:
                            print("...{} in department, parsing abstract and adding to dictonaries".format(person))
                            personList = [person]
                            abstractAuthors = unparsedAuthorsStep2.replace("<div class=\"paperauthors\">", "").replace("\t", "").replace("\r", "").replace("\n", "").replace("&#13;", "").replace("</div>", "") # removes characters I don't want.
                            if abstractTree.xpath('//span[@class="number"]/text()'):
                                abstractNumber = abstractTree.xpath('//span[@class="number"]/text()')[0] # Because xpath returns a list object with a single item, we have to plop the index on the end to get a string object. presuming there are no markup tags here
                            else:
                                pass
                            # if abstractTree.xpath('//div[@class="subtext"]/text()'):
                            unparsedabstractTitleStep1 = abstractTree.xpath('//div[@class="subtext"]') # Since there are markup tags in people's titles, so we have to go through the same process as with "authors" above...
                            for elem in unparsedabstractTitleStep1:
                                unparsedabstractTitleStep2 = etree.tostring(elem, pretty_print=True, encoding='unicode')
                                abstractTitle = unparsedabstractTitleStep2.replace("<div class=\"subtext\">", "").replace("</div>", "").replace("&#13;", "").replace("\n", "").replace("\t", "").replace("\r", "")
                            abstractTimeString = abstractTree.xpath('//div[@class="datetime"]/text()')[0] # we know there's no markup in this field so it's just a straight xpath grab.
                            if ":" in abstractTimeString: # this checks if the presentation has an hour:minute stamp: if it doesn't, it's a poster & not a talk, and adjusts datetime processing to suit
                                abstractTime = datetime.strptime(abstractTimeString, r"%A, %d %B %Y: %H:%M") # converts the presentation time from a string object to a datetime object for sorting later
                                abstractFormat = "talk"
                            else:
                                abstractTime = datetime.strptime(abstractTimeString, r"%A, %d %B %Y")
                                abstractFormat = "poster"

                            # Now we parse all this into the 2 dictonaries described above:
                            # The dictionary to be indexed by abstract URLs as the key:
                            abstractByURLDict[presentationURL] = {} # defining the primary key to this dictionary which creates a nested dictionary
                            abstractByURLDict[presentationURL]['deptPresenters'] = personList # creates a value in the nested dictionary
                            abstractByURLDict[presentationURL]['title'] = abstractTitle
                            abstractByURLDict[presentationURL]['authors'] = abstractAuthors
                            abstractByURLDict[presentationURL]['time'] = abstractTime
                            abstractByURLDict[presentationURL]['format'] = abstractFormat
print ("----------\nSuccess Building Dictionary!")
print("Done scraping!")


# %%
print("There are {} talks being given by department members at AGU this year!".format(len(abstractByURLDict.items())))

# %% [markdown]
# Now we want flip around the nested dictionary we just created into a different nested dictionary that's indexed by department presenter
#
# In order to do that we need to make a list of all of the department presenters in the above dictionary, but also prevent / remove duplicates from that list so we don't have duplicate entries in the dictionary we are going to create:
#

# %%
deptPresenterList= []
for key1, value1 in abstractByURLDict.items():
    for x in value1['deptPresenters']:
        if x in deptPresenterList:
            pass
        else:
            deptPresenterList.append(x)
print("There are {} department members presenting at AGU this year".format(len(deptPresenterList)))
for x in sorted(deptPresenterList):
    print(x)

# %% [markdown]
# Now we're ready to start generating some html from the URL dictionary above, and then from the list of names above that we're going to use to "query" against that URL dictionary.
#
# We want to generate a table of the talks in html, but we want the talks sorted by presentation time. To do that we need to sort the dictionary we made by presentation time.  I don't yet understand the following line of code w/r/t the lambda function, to be honest, but it's the recommended way of sorting a dictionary and since we're dealing with nested dictionaries it returns a list of dictionaries!  How cool is that?  It makes iterating through the dictionary to generate the html a lot easier.

# %%
sortedDict = sorted(abstractByURLDict.items(), key = lambda x:x[1]['time'])

for x in sortedDict:
    print(x)

# %% [markdown]
# Now we want to parse the html!
#
# There are some SNAFUs with encoding of special characters.  If I had more time I could delve into that as it probably stems from issues with the input or output encoding from lxml.
#
# The following block parses the above list of dictionaries into an html table of a schedule of talks for folks in the department.

# %%
with open(outputScheduleHTML,'a',encoding='utf-8') as outfile:
    day = ""
    lastTalkFormat = ""
    outfile.write("<p>U-Mass Geosciences has a strong showing at the (virtual) annual Fall meeting of the <a href=\"https://www.agu.org/fall-meeting\" target=\"_blank\">American Geophysical Union</a> this year, with {} department members presenting {} talks December 7th - 16th, 2020. If you're attending #AGU2020 this year don't miss out! Here is a schedule of who is presenting and when:</p><p>Click <a href=\"#index\">here</a> to browse the presentations by author.".format(len(abstractByURLDict.items()), len(deptPresenterList)))
    outfile.write("<table>")
    for x in sortedDict:
        currentDay = datetime.strftime(x[1]['time'], r"%A, %d %B %Y")
        if currentDay != day:
            outfile.write("<tr><td><h1>{}</h1></td></tr>".format(currentDay))
            day = currentDay
        else:
            day = currentDay

        if x[1]['format'] == "talk":
            time = datetime.strftime(x[1]['time'], r"%A, %d %B %Y - %I:%M %p")
            talkFormat = "Talk"
        else:
            time = datetime.strftime(x[1]['time'], r"%A, %d %B %Y")
            talkFormat = "Poster"

        if talkFormat != lastTalkFormat:
            if talkFormat == "Poster":
                outfile.write("<tr><td><h2>Posters:</h2></td></tr>")
            elif talkFormat == "Talk":
                outfile.write("<tr><td><h2>Talks:</h2></td></tr>")
        elif talkFormat == lastTalkFormat:
            pass
        else:
            print("WHOAH something is wrong here with parsing talk formats.")
            break
        lastTalkFormat = talkFormat

        authors = x[1]['authors']
        fixedAuthors = authors.replace("Ã±", "ñ").replace("Â", "").replace("Ã§", "ç") # fixing weird encoding issues
        title = x[1]['title']
        fixedTitle = title.replace("â", "-").replace("Ë", "˚").replace("\n", "").replace("\t", "").replace("\r", "").replace("Ã", "í")
        url = x[0]

        outfile.write("<tr><td>")
        # outfile.write("<p>")
        outfile.write("<a href=\"{}\" target=\"_blank\">{}</a><br>".format(url, fixedTitle))
        outfile.write("<em>{}</em>".format(time))
        outfile.write("<p>{}</p>".format(fixedAuthors))
        # outfile.write("</p>")
        outfile.write("</td></tr>")
    outfile.write("</table>")
print("Schedule of department presenters written to {}".format(outputScheduleHTML))

# %% [markdown]
# Now let's make an html table of talks organized by person!  This will append the table to the end of the html file above.
#
# We already have a nicely sorted list by time above, containing dictionary items for each talk.  We can iterate through the list of speakers we made a few blocks above and search through the list-of-dictionaries to populate that table:

# %%
with open(outputScheduleHTML,'a',encoding='utf-8') as outfile:
    outfile.write("<h1 id=\"index\">Index of Presenters</h1>")
    outfile.write("<table>")
    for person in sorted(deptPresenterList):
        outfile.write("<tr><td><h2>{}</h2></td></tr>".format(person))
        for x in sortedDict:
            if person not in x[1]['deptPresenters']:
                pass
            else:
                title = x[1]['title']
                fixedTitle = title.replace("â", "-").replace("Ë", "˚").replace("\n", "").replace("\t", "").replace("\r", "").replace("Ã", "í")
                url = x[0]

                if x[1]['format'] == "talk":
                    time = datetime.strftime(x[1]['time'], r"%A, %d %B %Y - %I:%M %p")
                else:
                    time = datetime.strftime(x[1]['time'], r"%A, %d %B %Y")

                outfile.write("<tr><td><a href=\"{}\" target=\"_blank\">{}</a></td></tr>".format(url, fixedTitle))
                outfile.write("<tr><td>{}</td></tr>".format(time))

print("Index of department presenters appended to {}".format(outputScheduleHTML))


# %%



