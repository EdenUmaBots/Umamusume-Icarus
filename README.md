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

Now.

Download Eden bot.

In cmd....

cd (file location) example: C:\Users\yourusernamehere\Downloads\Umamusume-API-Bot-main\Umamusume-API-Bot-main

winget install -e --id OpenJS.NodeJS 

npm i

Close and call bot in cd again

pip install -r requirements.txt (you will need an older ver of python for this)

# Running the bot!

Make sure your veteran umas are cleared and have no career in progress. Plenty of gems are needed as well. 

In cmd, cd file location then main.py. Bot will open steam and launch the game close in loading screen, paste the provided address in your browser and sign in using your Steam info, it will ask for a code sent to your email, provide that, and you're in. 

Recommended to use an alt Steam account. Make sure you have no (non-MANT) careers in progress. Rest should be self-explanatory.

# Running multiple bots!

Ensure you have multiple seperate folders and keep track. Each bot must have it's own port number, this is located in main.py, line 186, change it to something else, default is 1200, so second bot could be 1201. Each bot needs its own steam account.

Launch first bot until you're in web UI, switch steam accounts, repeat the process. Turn on each bot simoultaneously. First bot acts as an anchor, if this crashes, all bots will crash. We found that we were able to comfortably run 3 accounts at the same time, could try more.

Daily reset will cause the bots to crash, you must set everything up manually then. 













