FROM python:latest

# Set working directory
WORKDIR /usr/src/app

# Copy the files to the container
COPY . .

# Install required packages
RUN pip install --no-cache-dir -r requirements.txt

# Mount the folder
VOLUME /usr/src/app

# Run the main.py script
CMD ["python", "APRSFriendAlert.py"]
