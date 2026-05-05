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

4. Once the server is up and running, open the web terminal in the normal way
and look for a small "headphones" icon on the left side of the upper window,
right below the channel name.  Click on the icon and it a small "pause" symbol
should appear next to the headphones.  This signifies the stream is connected
and ready to play when audio is decoded by the receiver.  Click on the pause
symbol to stop playback.

5. If there are multiple channels defined, you presently have to cycle through
each channel and turn the audio on.  Once turned on, the channel will continue
to play simultaneously with any other enabled channels.
