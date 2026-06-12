# Music File Manager Ver 0.1.8
A simple music manager for renaming files and setting meta data.

Features:
1. Bulk renaming with a simple intuitive text box. 
2. Smart spacing for when you need to rename files and maintain spaces between title names but remove any extra spaces left by previous text you removed. (Toggable)
3. Delimiters allow for you to bulk delete strings between 2 values such as []. Meaning song names with [ExtraName] Song Title.mp3 would be easily fixed by adding [] in the rule set deleting the brackets and the content inside. However this feature is seperate from the main rule box allowing you to customise song titles without this feature making unwanted changes.
4. Assign an index to your tracklist with ease, simply move the songs up and down according to how the album is structured and click on "Use table order as Track #".
5. Bulk tag editing for Contributing Artist, Album Artist, Album, Year, Title, and Genre.
6. Live warnings that react to pending edits, including duplicate track numbers.
7. Extract track numbers and tag values from filenames.
8. Change, remove and even clone album art onto different tracks. (Jpeg/Png supported.)
9. Create, load, update, and delete multiple named cleanup and extraction rule sets, with a built-in Default set.
10. Light and dark themes.

Themes are saved separately from rule sets, so loading another set never changes the app's appearance.

# Releases
I have released my first Windows version of the app!
Please head to [the releases page](https://github.com/bw0p/MusicManager/releases) for the latest release.

As of now, I have no plans on releasing a Mac or Linux version unless there is enough interest.

# How to run
If you plan on making edits and need a better way to debug follow this guide:

I use VS Code so im not sure how this would work on other IDEs (or if you're running this off a terminal without VS Code).

For VS Code make sure you have the Python extension downloaded!!

In your terminal paste in these 1 by 1:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
python app.py
```

If you get a permission issue you may also use 
```powershell
.\.venv\Scripts\activate.bat
```
Or the following however the previous solution is easier.
```
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& YOURDRIVE:\FILEPATH\MusicManager\.venv\Scripts\Activate.ps1)  
```

Or make use of the built in VS code debugging that will use the launch.json. Just make sure you're on app.py when you click on run.

# Issues
None as of now

# To Do
1. Undo using an apply log/backup record.