# Music File Manager Ver 0.1.2
A simple music manager for renaming files and setting meta data.

Features:
1. Bulk renaming with a simple intuitive text box. 
2. Smart spacing for when you need to rename files and maintain spaces between title names but remove any extra spaces left by previous text you removed. (Toggable)
3. Delimiters allow for you to bulk delete strings between 2 values such as []. Meaning song names with [ExtraName] Song Title.mp3 would be easily fixed by adding [] in the rule set deleting the brackets and the content inside. However this feature is seperate from the main rule box allowing you to customise song titles without this feature making unwanted changes.
4. Assign an index to your tracklist with ease, simply move the songs up and down according to how the album is structured and click on "Use table order as Track #".
5. Bulk Album artist editing. The app allows you to select multiple songs with ctrl + left click allowing you to change multiple songs' Album Artist.

# How to run
I use VS Code so im not sure how this would work on other IDEs.

For VS Code make sure you have the Python extension downloaded!!

```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install mutagen
python app.py
```

Or I think hitting run debugging should make use of the .json (you still need an environment)

Eventually I will be releasing an exe file but you're free to use the repo itself to run the software.

# Issues
None as of now

# To Do
1. Make warnings refresh when you provide requested data (such as adding an album artist should remove no album artist warning).
2. Allow user to change contributing artists for all or selected.
3. Allow user to change Year for all or selected.
4. Allow user to change Genre for all or selected.
5. Allow user to change Album for all or selected.
6. Allow user to change/set album art for all or selected.
7. Saving for settings.
8. Dark Theme.
9. Undo (perhaps a log file to undo changes)
