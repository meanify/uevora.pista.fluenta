# base python image for custom image
FROM python:3.14.2-alpine

# create working directory and install pip dependencies
WORKDIR /opt/app
COPY pistadigital/ pistadigital/
COPY exports/ exports/
COPY lime_flows.py ine_flows.py ./
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# run the flask server  
ENTRYPOINT ["python3", "lime_flows.py"]
CMD ["all", "-s", "666914"]