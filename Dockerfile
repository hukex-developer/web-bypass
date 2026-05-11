# Use Playwright's official Python image as the base
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set up work directory
WORKDIR /app

# Copy the script
COPY persistent_bot.py .

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt
# Browser dependencies are already in the base image, but we ensure chromium is installed
RUN playwright install chromium

# Run the bot
CMD ["python", "persistent_bot.py"]
