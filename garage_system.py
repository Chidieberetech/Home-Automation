# Main Controller for Garage System
# 
# This system controls a garage door using various inputs:
# - License plate recognition via camera
# - Voice commands
# - MQTT messages
#
# Camera Preview Feature:
# - Press 'p' to toggle the camera preview window
# - Use the preview to position the camera for optimal license plate recognition
# - The preview shows a crosshair to help with alignment
# - Press 'p' again to hide the preview
# - Press 'q' to quit the application


import json
import time
import threading
import cv2
import pyaudio
import speech_recognition as sr
import paho.mqtt.client as mqtt
import boto3
import garage_config
import os
from botocore.exceptions import ClientError


class GarageSystem:
    def __init__(self):
        self.secrets = self.get_secrets()
        self.door_open = False
        self.auto_close_timer = None
        self.mqtt_client = self.setup_mqtt()
        self.preview_enabled = True  # Flag to control camera preview - enabled by default
        self.preview_window_name = "Camera Preview"

        # Initialize camera with error handling
        try:
            self.camera = cv2.VideoCapture(1)  # Use external camera (index 1)
            if not self.camera.isOpened():
                raise Exception("Could not open camera")
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.camera_available = True
            print("Camera initialized successfully (Logitech 720 external camera)")
        except Exception as e:
            print(f"Error initializing camera: {e}")
            print("System will continue without camera functionality")
            self.camera = None
            self.camera_available = False

        self.last_frame = None

        # Initialize speech recognition
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            self.voice_available = True
        except Exception as e:
            print(f"Error initializing speech recognition: {e}")
            print("System will continue without voice recognition")
            self.voice_available = False

        # Start subsystems
        threading.Thread(target=self.camera_monitor, daemon=True).start()
        if self.voice_available:
            threading.Thread(target=self.voice_monitor, daemon=True).start()

        # Start MQTT loop in a separate thread with error handling
        try:
            threading.Thread(target=self.mqtt_client.loop_forever, daemon=True).start()
        except Exception as e:
            print(f"Error starting MQTT loop: {e}")

        print("Garage System Started. Press Ctrl+C to exit.")

    def get_secrets(self):
        """Load configuration from garage_config.py"""
        # Return configuration values
        return {
            'IOT_ENDPOINT': garage_config.IOT_ENDPOINT,
            'SECRET_TOKEN': garage_config.SECRET_TOKEN,
            'AuthorizedPlates': garage_config.AUTHORIZED_PLATES_TABLE
        }

    def setup_mqtt(self):
        """Configure MQTT connection to AWS IoT Core"""
        client = mqtt.Client(client_id="garage_controller")

        try:
            # Check if required files exist
            cert_files = ['root-CA.crt', 'certificate.pem.crt', 'private.pem.key']
            missing_files = [f for f in cert_files if not os.path.isfile(f)]

            if missing_files:
                print(f"Warning: Missing certificate files: {', '.join(missing_files)}")
                print("MQTT connection will be attempted without TLS")
            else:
                client.tls_set(
                    ca_certs='root-CA.crt',
                    certfile='certificate.pem.crt',
                    keyfile='private.pem.key'
                )

            # Ensure IOT_ENDPOINT exists in secrets
            if 'IOT_ENDPOINT' not in self.secrets:
                print("Warning: IOT_ENDPOINT not found in secrets, using default")
                self.secrets['IOT_ENDPOINT'] = 'iot-endpoint.amazonaws.com'

            # Try to connect
            client.connect(self.secrets['IOT_ENDPOINT'], 8883)
            client.on_connect = self.on_connect
            client.on_message = self.on_message
            print(f"MQTT client connected to {self.secrets['IOT_ENDPOINT']}")

        except Exception as e:
            print(f"Error setting up MQTT: {e}")
            print("System will continue without MQTT functionality")

        return client

    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        print(f"Connected to AWS IoT with code {rc}")
        client.subscribe("garage/control")

    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            payload = json.loads(msg.payload.decode())

            # Validate token if security is enabled
            if 'SECRET_TOKEN' in self.secrets:
                if not payload.get('token') or payload.get('token') != self.secrets['SECRET_TOKEN']:
                    print("Invalid command token rejected")
                    return

            # Process commands
            command = payload.get('command', '')
            if command == 'open' and not self.door_open:
                self.open_door()
            elif command == 'close' and self.door_open:
                self.close_door()
            elif command:
                print(f"Received command: {command} - no action taken")
            else:
                print("Received message with no command")

        except json.JSONDecodeError:
            print("Invalid MQTT payload")
        except Exception as e:
            print(f"Error processing message: {e}")

    def detect_motion(self, frame):
        """Simple motion detection algorithm"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if self.last_frame is None:
                self.last_frame = gray
                return False

            frame_delta = cv2.absdiff(self.last_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]

            # Create a proper kernel for dilation
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.dilate(thresh, kernel, iterations=2)

            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if cv2.contourArea(contour) > 5000:  # Minimum contour area
                    return True

            self.last_frame = gray
            return False
        except Exception as e:
            print(f"Error in motion detection: {e}")
            return False

    def process_plate(self, frame):
        """Detect and validate license plate using AWS Rekognition and DynamoDB"""
        try:
            # Check if required configuration exists
            if 'AuthorizedPlates' not in self.secrets:
                print("Error: AuthorizedPlates not configured in secrets")
                return False

            # Use AWS credentials from garage_config

            # Create AWS clients with explicit credentials
            rekognition = boto3.client(
                'rekognition',
                aws_access_key_id=garage_config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=garage_config.AWS_SECRET_ACCESS_KEY,
                region_name=garage_config.AWS_REGION
            )
            dynamodb = boto3.resource(
                'dynamodb',
                aws_access_key_id=garage_config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=garage_config.AWS_SECRET_ACCESS_KEY,
                region_name=garage_config.AWS_REGION
            )
            table = dynamodb.Table(self.secrets['AuthorizedPlates'])

            # Convert frame to bytes
            _, img_encoded = cv2.imencode('.jpg', frame)
            image_bytes = img_encoded.tobytes()

            # Detect plate text
            try:
                print("Sending image to AWS Rekognition for text detection")
                response = rekognition.detect_text(Image={'Bytes': image_bytes})

                # Print all detected text for debugging
                all_detections = response.get('TextDetections', [])
                print(f"Rekognition detected {len(all_detections)} text elements")

                for i, detection in enumerate(all_detections):
                    print(f"  Text {i+1}: '{detection.get('DetectedText')}' (Type: {detection.get('Type')}, Confidence: {detection.get('Confidence'):.1f}%)")

                # Filter for high-confidence line text
                plates = [t['DetectedText'] for t in all_detections
                          if t['Type'] == 'LINE' and t['Confidence'] > 80]

                print(f"Filtered to {len(plates)} potential license plates: {plates}")

                if not plates:
                    print("No license plate detected with sufficient confidence")
                    return False
            except ClientError as e:
                print(f"AWS Rekognition error: {e}")
                return False

            # Clean and validate plate
            plate_clean = ''.join([char for char in plates[0] if char.isalnum()]).upper()
            print(f"Cleaned plate text: '{plate_clean}'")

            try:
                print(f"Checking if plate '{plate_clean}' is authorized in DynamoDB")
                response = table.get_item(Key={'plate': plate_clean})

                if 'Item' in response:
                    print(f"Authorized plate confirmed: {plate_clean}")
                    print(f"Plate details: {response['Item']}")
                    return True
                else:
                    print(f"Plate not found in authorized database: {plate_clean}")
                    return False
            except ClientError as e:
                print(f"DynamoDB error: {e}")
                return False

        except Exception as e:
            print(f"Error in license plate processing: {e}")
            return False

    def open_door(self):
        """Handle door opening"""
        print("GARAGE DOOR OPENING")
        self.door_open = True

        # Start auto-close timer
        if self.auto_close_timer:
            self.auto_close_timer.cancel()

        self.auto_close_timer = threading.Timer(
            120.0,  # 2 minutes
            self.close_door
        )
        self.auto_close_timer.start()

        # Publish state update
        try:
            # Ensure SECRET_TOKEN exists
            token = self.secrets.get('SECRET_TOKEN', 'default-token')

            # Create message payload
            payload = {
                "state": "open",
                "timestamp": int(time.time()),
                "token": token
            }

            # Convert to JSON string
            payload_str = json.dumps(payload)
            print(f"Publishing to garage/state: {payload_str}")

            # Publish message
            result = self.mqtt_client.publish(
                "garage/state",
                payload_str
            )

            # Check if message was queued successfully
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print("MQTT message queued successfully")
            else:
                print(f"MQTT publish error: {result.rc}")

        except Exception as e:
            print(f"Error publishing door state: {e}")
            print("Door operation will continue without MQTT update")

    def close_door(self):
        """Handle door closing"""
        print("GARAGE DOOR CLOSING")
        self.door_open = False

        if self.auto_close_timer:
            self.auto_close_timer.cancel()
            self.auto_close_timer = None

        # Publish state update
        try:
            # Ensure SECRET_TOKEN exists
            token = self.secrets.get('SECRET_TOKEN', 'default-token')

            # Create message payload
            payload = {
                "state": "closed",
                "timestamp": int(time.time()),
                "token": token
            }

            # Convert to JSON string
            payload_str = json.dumps(payload)
            print(f"Publishing to garage/state: {payload_str}")

            # Publish message
            result = self.mqtt_client.publish(
                "garage/state",
                payload_str
            )

            # Check if message was queued successfully
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print("MQTT message queued successfully")
            else:
                print(f"MQTT publish error: {result.rc}")

        except Exception as e:
            print(f"Error publishing door state: {e}")
            print("Door operation will continue without MQTT update")

    def camera_monitor(self):
        """Continuously monitor camera for motion and plates"""
        print("Camera monitor started")

        # Check if camera is available
        if not hasattr(self, 'camera_available') or not self.camera_available:
            print("Camera not available. Camera monitoring disabled.")
            return

        last_detection_time = 0
        COOLDOWN = 30  # Seconds between detections

        while True:
            try:
                # Check if camera is still available
                if self.camera is None or not self.camera.isOpened():
                    print("Camera disconnected. Attempting to reconnect...")
                    try:
                        self.camera = cv2.VideoCapture(1)  # Use external camera (index 1)
                        if not self.camera.isOpened():
                            print("Failed to reconnect to camera")
                            time.sleep(10)  # Wait before trying again
                            continue
                        print("Camera reconnected successfully (Logitech 720 external camera)")
                    except Exception as e:
                        print(f"Error reconnecting to camera: {e}")
                        time.sleep(10)
                        continue

                ret, frame = self.camera.read()
                if not ret:
                    print("Failed to read frame from camera")
                    time.sleep(1)
                    continue

                # Show preview if enabled
                self.show_preview(frame)

                current_time = time.time()

                # Check for motion
                if current_time - last_detection_time > COOLDOWN:
                    motion_detected = self.detect_motion(frame)
                    print(f"Motion detection result: {motion_detected}")

                    if motion_detected:
                        print("Motion detected - checking license plate")
                        plate_result = self.process_plate(frame)
                        print(f"License plate detection result: {plate_result}")

                        if plate_result:
                            print("Authorized plate detected - opening door")
                            self.open_door()
                            last_detection_time = current_time
                        else:
                            print("No authorized plate detected - door remains closed")

            except Exception as e:
                print(f"Error in camera monitoring: {e}")

            time.sleep(0.1)

    def toggle_preview(self):
        """Toggle camera preview window on/off"""
        if not self.camera_available:
            print("Camera not available. Cannot show preview.")
            return

        self.preview_enabled = not self.preview_enabled

        if self.preview_enabled:
            print("Camera preview enabled. Press 'p' to disable.")
        else:
            print("Camera preview disabled.")
            # Close the preview window if it exists
            cv2.destroyWindow(self.preview_window_name)

    def show_preview(self, frame):
        """Display camera preview window for positioning"""
        if self.preview_enabled and frame is not None:
            # Add text overlay with instructions
            preview_frame = frame.copy()
            cv2.putText(
                preview_frame,
                "Camera Preview - Press 'p' to hide",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            # Add crosshair to help with positioning
            h, w = preview_frame.shape[:2]
            cv2.line(preview_frame, (w//2, 0), (w//2, h), (0, 255, 0), 1)
            cv2.line(preview_frame, (0, h//2), (w, h//2), (0, 255, 0), 1)

            # Display the frame
            cv2.imshow(self.preview_window_name, preview_frame)

            # Check for 'p' key press to toggle preview
            key = cv2.waitKey(1) & 0xFF
            if key == ord('p'):
                self.toggle_preview()

    def voice_monitor(self):
        """Continuously listen for voice commands"""
        print("Voice monitor started")

        # Initialize microphone with error handling
        try:
            with self.microphone as source:
                print("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source)
                print("Voice recognition ready")
        except Exception as e:
            print(f"Error initializing microphone: {e}")
            print("Voice recognition disabled")
            return

        # Command keywords
        COMMANDS = {
            'open': ['open', 'garage', 'door'],
            'close': ['close', 'shut', 'garage', 'door']
        }

        while True:
            try:
                with self.microphone as source:
                    print("Listening for commands...")
                    audio = self.recognizer.listen(source, timeout=5)

                text = self.recognizer.recognize_google(audio).lower()
                print(f"Recognized: {text}")

                # Process commands
                words = set(text.split())

                # Check for open command
                if all(keyword in words for keyword in ['open', 'garage']):
                    if not self.door_open:
                        print("Voice command recognized: OPEN")
                        self.open_door()
                    else:
                        print("Door already open")

                # Check for close command
                elif any(keyword in words for keyword in ['close', 'shut']) and 'garage' in words:
                    if self.door_open:
                        print("Voice command recognized: CLOSE")
                        self.close_door()
                    else:
                        print("Door already closed")

            except sr.UnknownValueError:
                # Common - no speech detected
                pass
            except sr.RequestError as e:
                print(f"Speech service error: {e}")
                print("Waiting 30 seconds before retrying...")
                time.sleep(30)  # Back off on service errors
            except sr.WaitTimeoutError:
                # Common - no speech detected within timeout
                pass
            except Exception as e:
                print(f"Unexpected error in voice recognition: {e}")

            # Small delay between recognition attempts
            time.sleep(1)


def check_keyboard_input(system):
    """Check for keyboard input to control the system"""
    import msvcrt

    print("\nKeyboard controls:")
    print("  'p' - Toggle camera preview for positioning")
    print("  'q' - Quit the application")

    while True:
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8').lower()
            if key == 'p':
                system.toggle_preview()
            elif key == 'q':
                print("\nSystem shutting down")
                break
        time.sleep(0.1)

if __name__ == "__main__":
    system = GarageSystem()
    try:
        # Start keyboard input monitoring in a separate thread
        keyboard_thread = threading.Thread(target=check_keyboard_input, args=(system,), daemon=True)
        keyboard_thread.start()

        print("\nGarage System running. Press 'p' to show camera preview, 'q' to quit.")

        # Main loop
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSystem shutting down")
