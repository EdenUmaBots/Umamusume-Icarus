# # Instructions.

# Capable of 200M+ fans per day/ 5min MANT runs, all previous restrictions removed, multiple accounts can be run simultaneously.
<img width="1216" height="106" alt="image" src="https://github.com/user-attachments/assets/6b0a2c0b-4268-4b2d-8fee-69f0b3160cea" />

# TLDR: Spam Sweepy logo until the "dev" button pops up, click it and "tempt fate", that's it!
<img width="1876" height="86" alt="image" src="https://github.com/user-attachments/assets/b5bee15f-1d6e-46f6-8779-f6a79f443c79" />

<img width="1080" height="262" alt="image" src="https://github.com/user-attachments/assets/41fb609c-9c3b-4624-a956-f38143f95b11" />

T500 to T10 in 4 days btw.

Join our discord: https://discord.gg/wpbd3hTBDc

# ! Instalation for dummies:

You will need the latest version of python and C++ Build Tools:

https://www.python.org/downloads/

https://visualstudio.microsoft.com/visual-cpp-build-tools/

For C++ Tools, this is what you need, just check that box. <img width="1221" height="625" alt="image" src="https://github.com/user-attachments/assets/28610cb3-650d-43c9-bf09-4505a62272de" />

# First time instalation:

Step 1: Download bot directly from this repo, unzip file

Step 2: Open the bot folder (usually second one) in cmd like this, please note, this is an example link, yours will be different.

```cmd
cd C:\Users\yourusernamehere\Downloads\Umamusume-API-Bot-main\Umamusume-API-Bot-main
```
Step 3: Paste the following lines in order. 

```cmd
winget install -e --id OpenJS.NodeJS
```
Accept terms, then:

```cmd
npm i
```
Disregard the error you might have here, then:

```cmd
pip install -r requirements.txt 
```
Once the above it done, paste or type:

```cmd
python main.py
```

The bot will launch steam and umamusume then promptly close the game shortly before fully loading in, you will be given a web address, please paste this into your browser, you will be promted to log into your steam account, (it is recommended to use an alt). Web UI will request a steamguard code, once provided, you're in! Everything from here should be self explanitory. 

# Running multiple bots!

Ensure you have multiple seperate folders and keep track. Each bot must have it's own port number, this is located in main.py, line 186, change it to something else, default is 1200, so second bot could be 1201. Each bot needs its own steam account.

Launch first bot until you're in web UI, switch steam accounts, repeat the process. Turn on each bot simoultaneously. First bot acts as an anchor, if this crashes, all bots will crash. We found that we were able to comfortably run 3 accounts at the same time, could try more.

Daily reset will cause the bots to crash, you must set everything up manually then. 

# Future updates.

We will be working towards updating the bot as we see fit and will be porting it over to new scenarios, if you would like to contribute, get in touch with us though discord. Clank responsibly and thank you all. 













