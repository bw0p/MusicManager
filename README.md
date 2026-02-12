# Music File Manager Ver 0.1.1
A simple music manager for renaming files and setting meta data.

Features:
1. Bulk renaming with a simple intuitive text box. 
2. Smart spacing for when you need to rename files and maintain spaces between title names but remove any extra spaces left by previous text you removed. (Toggable)
3. Delimiters allow for you to bulk delete strings between 2 values such as []. Meaning song names with [ExtraName] Song Title.mp3 would be easily fixed by adding [] in the rule set deleting the brackets and the content inside. However this feature is seperate from the main rule box allowing you to customise song titles without this feature making unwanted changes.

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