# Main Controller for Garage System
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
import subprocess
import sys
import ssl
from botocore.exceptions import ClientError


class GarageSystem:
    def __init__(self):
        self.door_open = False
        self.auto_close_timer = None
        self.mqtt_client = self.setup_mqtt()
        self.preview_enabled = True
        self.preview_window_name = "Camera Preview"
        self.shutdown_event = threading.Event()
        self.simulator_process = None
        self.camera_available = False
        self.voice_available = False

        # Launch simulator automatically
        self.launch_simulator()

        # Initialize camera
        self.initialize_camera()

        # Initialize speech recognition
        self.initialize_voice_recognition()

        # Start subsystems
        threading.Thread(target=self.camera_monitor, daemon=True).start()
        if self.voice_available:
            threading.Thread(target=self.voice_monitor, daemon=True).start()

        # Start MQTT loop
        try:
            threading.Thread(target=self.mqtt_client.loop_forever, daemon=True).start()
        except Exception as e:
            print(f"Error starting MQTT loop: {e}")

        print("Garage System Started. Press 'p' to toggle preview, 'q' to exit.")
        threading.Thread(target=self.check_keyboard_input, daemon=True).start()

    def launch_simulator(self):
        """Launch the garage simulator automatically"""
        try:
            simulator_path = "garage_simulator.py"
            if not os.path.exists(simulator_path):
                print(f"Warning: {simulator_path} not found")
                return

            print("Launching garage simulator...")
            self.simulator_process = subprocess.Popen(
                [sys.executable, simulator_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            time.sleep(2)  # Give simulator time to start

            if self.simulator_process.poll() is None:
                print("Garage simulator launched successfully")
            else:
                print("Failed to launch garage simulator")
                _, stderr = self.simulator_process.communicate()
                if stderr:
                    print(f"Simulator error: {stderr}")

        except Exception as e:
            print(f"Error launching simulator: {e}")

    def initialize_camera(self):
        """Initialize the Logitech 720 external camera"""
        try:
            # Try common camera indices
            for index in [1, 2, 0, 3, 4]:
                try:
                    camera = cv2.VideoCapture(index)
                    if camera.isOpened():
                        ret, frame = camera.read()
                        if ret and frame is not None:
                            self.camera = camera
                            self.camera_available = True
                            print(f"Camera initialized at index {index}")
                            return
                    camera.release()
                except:
                    continue

            print("Camera not found")
            self.camera_available = False
        except Exception as e:
            print(f"Camera init error: {e}")
            self.camera_available = False

    def initialize_voice_recognition(self):
        """Initialize speech recognition system"""
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            self.voice_available = True
            print("Voice recognition initialized")
        except Exception as e:
            print(f"Voice init error: {e}")
            self.voice_available = False

    def setup_mqtt(self):
        try:
            client = mqtt.Client(
                client_id="garage_controller",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )
            client.on_connect = self.on_connect
            client.on_disconnect = self.on_disconnect
            client.on_message = self.on_message

            # Configure TLS
            client.tls_set(
                ca_certs='root-CA.crt',
                certfile='GarageController.cert.pem',
                keyfile='GarageController.private.key',
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS
            )

            print(f"Connecting to AWS IoT: {garage_config.IOT_ENDPOINT}")
            client.connect(garage_config.IOT_ENDPOINT, 8883, 60)
            return client

        except Exception as e:
            print(f"MQTT setup failed: {e}")
            return mqtt.Client(
                client_id="garage_controller_offline",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            print(f"Connection failed: {reason_code}")
            return

        print("Connected to AWS IoT")
        client.subscribe("garage/control")

    def on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            print(f"Unexpected disconnect: {reason_code}")

    def on_message(self, client, userdata, msg, properties=None):
        try:
            payload = json.loads(msg.payload.decode())

            # Validate token
            if payload.get('token') != garage_config.SECRET_TOKEN:
                print("Invalid token rejected")
                return

            # Process commands
            command = payload.get('command', '')
            if command == 'open' and not self.door_open:
                self.open_door()
            elif command == 'close' and self.door_open:
                self.close_door()
        except:
            print("Invalid MQTT payload")

    def detect_motion(self, frame):
        """Simple motion detection"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if not hasattr(self, 'last_frame') or self.last_frame is None:
                self.last_frame = gray
                return False

            frame_delta = cv2.absdiff(self.last_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if cv2.contourArea(contour) > 5000:
                    return True

            self.last_frame = gray
            return False
        except:
            return False

    def process_plate(self, frame):
        """Detect and validate license plate"""
        try:
            # Create AWS clients
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
            table = dynamodb.Table(garage_config.AUTHORIZED_PLATES_TABLE)

            # Convert frame to bytes
            _, img_encoded = cv2.imencode('.jpg', frame)
            response = rekognition.detect_text(Image={'Bytes': img_encoded.tobytes()})

            # Find best plate candidate with proper type checking
            plates = []
            for t in response['TextDetections']:
                if t['Type'] == 'LINE' and t['Confidence'] > 80:
                    plates.append(t['DetectedText'])

            if not plates:
                return False

            # Clean and validate plate
            plate_clean = ''.join(filter(str.isalnum, plates[0])).upper()
            response = table.get_item(Key={'plate': plate_clean})
            return 'Item' in response

        except Exception as e:
            print(f"Plate processing error: {e}")
            return False

    def open_door(self):
        print("GARAGE DOOR OPENING")
        self.door_open = True
        if self.auto_close_timer:
            self.auto_close_timer.cancel()
        self.auto_close_timer = threading.Timer(300.0, self.close_door)  # 5 minutes
        self.auto_close_timer.start()
        self.publish_door_state("open")

    def close_door(self):
        print("GARAGE DOOR CLOSING")
        self.door_open = False
        if self.auto_close_timer:
            self.auto_close_timer.cancel()
            self.auto_close_timer = None
        self.publish_door_state("closed")

    def publish_door_state(self, state):
        try:
            payload = {
                "state": state,
                "timestamp": int(time.time()),
                "token": garage_config.SECRET_TOKEN
            }
            self.mqtt_client.publish("garage/state", json.dumps(payload))
        except:
            print("Failed to publish state")

    def camera_monitor(self):
        if not self.camera_available:
            print("Camera monitoring disabled")
            return

        print("Camera monitor started")
        last_detection_time = 0
        COOLDOWN = 30

        while not self.shutdown_event.is_set():
            try:
                ret, frame = self.camera.read()
                if not ret:
                    time.sleep(1)
                    continue

                self.show_preview(frame)

                current_time = time.time()
                if current_time - last_detection_time > COOLDOWN:
                    if self.detect_motion(frame):
                        if self.process_plate(frame):
                            self.open_door()
                            last_detection_time = current_time
            except:
                pass

            time.sleep(0.1)

    def show_preview(self, frame):
        if self.preview_enabled and frame is not None:
            preview_frame = frame.copy()
            cv2.putText(preview_frame, "Press 'p' to hide",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow(self.preview_window_name, preview_frame)
            cv2.waitKey(1)

    def toggle_preview(self):
        self.preview_enabled = not self.preview_enabled
        if not self.preview_enabled:
            cv2.destroyWindow(self.preview_window_name)

    def voice_monitor(self):
        if not self.voice_available:
            return

        print("Voice monitor started")

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)

        while not self.shutdown_event.is_set():
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=5)
                text = self.recognizer.recognize_google(audio).lower()

                if "open" in text and "garage" in text and not self.door_open:
                    self.open_door()
                elif "close" in text and "garage" in text and self.door_open:
                    self.close_door()
            except:
                pass

            time.sleep(1)

    def check_keyboard_input(self):
        while not self.shutdown_event.is_set():
            try:
                if sys.platform == "win32":
                    import msvcrt
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode().lower()
                        if key == 'p':
                            self.toggle_preview()
                        elif key == 'q':
                            self.shutdown()
                else:
                    import select
                    if select.select([sys.stdin], [], [], 0)[0]:
                        key = sys.stdin.readline().strip().lower()
                        if key == 'p':
                            self.toggle_preview()
                        elif key == 'q':
                            self.shutdown()
            except:
                pass
            time.sleep(0.1)

    def shutdown(self):
        print("Shutting down system...")
        self.shutdown_event.set()

        if self.simulator_process:
            try:
                self.simulator_process.terminate()
            except:
                pass

        if self.auto_close_timer:
            self.auto_close_timer.cancel()

        if self.camera_available:
            self.camera.release()

        cv2.destroyAllWindows()

        try:
            self.mqtt_client.disconnect()
        except:
            pass

        os._exit(0)


if __name__ == "__main__":
    system = GarageSystem()
    try:
        while not system.shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        system.shutdown()