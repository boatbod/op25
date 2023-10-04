FROM debian:bullseye-slim
# Envinronmental arguaments (allow users to adjust their configs upon running container)
ENV config_file="config.json"
# Update, clone op25 from Github and build
RUN apt update \
&& apt upgrade -y \
&& apt install -y gnuradio-dev gr-osmosdr librtlsdr-dev libuhd-dev libhackrf-dev libitpp-dev libpcap-dev liborc-dev cmake git swig build-essential pkg-config doxygen python3-numpy python3-waitress python3-requests gnuplot-x11 \
&& cd /run \
&& git clone https://github.com/boatbod/op25.git \
&& cd op25 \
&& rm -rf build \
&& mkdir build \
&& cd build \
&& cmake ../ \
&& make \
&& make install \
&& ldconfig \
&& apt remove -y cmake build-essential git \
&& apt clean
WORKDIR /run/op25/gr-op25_repeater/apps
COPY $config_file /run/op25/gr-op25_repeater/apps/
EXPOSE 8080
CMD ["python3","/run/op25/op25/gr-op25_repeater/apps/multi_rx.py","-c","$config_file"]
