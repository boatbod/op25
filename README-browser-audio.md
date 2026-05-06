As of 5/4/2026, op25 has the capability to stream live audio to the web-based
terminal window across a network. There are several configuration steps that
must be in place for this to work.

i. Pull the latest code changes from https://github.com/boatbod/op25, build
and install it.
    cd ~/op25
    git pull        # <<< make sure there are no errors
    ./rebuild.sh

2. Browser audio capability only applies to the "New UI", which means it
only works with the multi_rx.py version of the app.

3. Audio streams via websockets which can run in parallel with the existing
udp based stream.  The server configuration must include a ws: destination
for each channel that you want to stream to the browser.
    "destination": "udp://127.0.0.1:23456, ws://0.0.0.0:9000",
or
    "destination": "ws://0.0.0.0:9000",
If you use the loopback address (127.0.0.1) you will only be able to connect
locally on the same machine.  Using 0.0.0.0 means connections will be accepted
on all interfaces.  Each channel needs it's own unique websocket port.  
Port 9000 is a suggested default, but by no means special.  If there are three
channels you might use 9000, 9001, and 9002 respectively.

4. Audio is streamed on all channels configured with a websocket by default. However, modern browser security requires the user to create AudioContext in order for the audio to play. You should be able to click anywhere in the UI with most browsers to create AudioContext and play the audio. Depending on your browser and security settings, you may have to actually interact with a button or menu for your browser to allow the audio to play.

5. If you want to not play audio by default, you can toggle "Mute Browser Audio at Startup" in the Settings Menu. If you have strict browser history and local storage settings configured, this setting may not be retained between program launches.
