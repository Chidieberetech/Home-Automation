# House Automation System

A comprehensive home automation system focusing on garage door control using Python, AWS services, and IoT technologies.

## Project Overview

This project implements a smart garage door system with the following features:

- Automated garage door control via MQTT
- License plate recognition for authorized vehicle access
- Motion detection for security
- Voice command recognition
- Simulation interface for testing and demonstration

## Components

### 1. Garage System (garage_system.py)

The main controller that handles:
- Camera monitoring and motion detection
- License plate recognition using AWS Rekognition
- Voice command processing
- MQTT communication with AWS IoT Core
- Automatic door closing after 2-minute timeout

### 2. Garage Simulator (garage_simulator.py)

A PyGame-based visual simulator that:
- Displays the garage door state (open/closed)
- Animates the door movement
- Connects to the same MQTT topics for real-time updates

## Prerequisites

- Python 3.7+
- AWS account with the following services configured:
  - AWS IoT Core
  - AWS Secrets Manager
  - AWS Rekognition
  - DynamoDB
- Required Python packages:
  ```
  opencv-python
  pyaudio
  SpeechRecognition
  paho-mqtt
  boto3
  pygame
  ```

## Setup Instructions

1. Clone this repository
2. Install required packages:
   ```
   pip install -r requirements.txt
   ```
3. Configure AWS services:
   - Create a DynamoDB table for license plate whitelist
   - Set up AWS IoT Core and download certificates
   - Store credentials in AWS Secrets Manager

4. Place AWS IoT certificates in the project directory:
   - root-CA.pem
   - certificate.pem
   - private.key

5. Update the IoT endpoint in garage_simulator.py with your AWS IoT endpoint

## Usage

1. Start the garage system:
   ```
   python garage_system.py
   ```

2. Start the simulator in a separate terminal:
   ```
   python garage_simulator.py
   ```

3. Control methods:
   - Voice commands ("close garage")
   - Authorized vehicle detection
   - MQTT messages to "garage/control" topic

## Security Features

- Token-based authentication for MQTT commands
- License plate whitelist validation
- Credentials stored securely in AWS Secrets Manager

## License

MIT
