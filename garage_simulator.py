import pygame
import json
import threading
import time
import sys
import os
import garage_config

# Try to use AWS IoT SDK first, fallback to paho-mqtt
try:
    from awsiot import mqtt_connection_builder
    from awscrt import mqtt, auth, io
    USE_AWS_SDK = True
    print("Using AWS IoT Device SDK for more reliable connection")
except ImportError:
    import paho.mqtt.client as mqtt
    import ssl
    USE_AWS_SDK = False
    print("Using paho-mqtt library")


class GarageSimulator:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((600, 600))
        pygame.display.set_caption("Garage Door Simulator")
        self.clock = pygame.time.Clock()
        self.door_height = 0
        self.door_open = False
        self.connected = False
        self.running = True
        self.last_update_time = time.time()
        self.connection_attempts = 0
        self.max_connection_attempts = 5

        # Setup MQTT client based on available SDK
        if USE_AWS_SDK:
            self.setup_aws_iot_connection()
        else:
            self.setup_paho_mqtt_connection()

    def setup_aws_iot_connection(self):
        """Setup AWS IoT connection using the official AWS SDK"""
        try:
            # Validate certificate files exist with correct names
            cert_files = ['root-CA.crt', 'GarageController.cert.pem', 'GarageController.private.key']
            for cert_file in cert_files:
                if not os.path.exists(cert_file):
                    print(f"Error: Certificate file {cert_file} not found!")
                    print("Running in offline mode - simulator will not receive real-time updates")
                    return

            print("Setting up AWS IoT Device SDK connection...")
            print(" Note: If connection fails, check AWS IoT Thing policies and certificate attachment")

            # Build MQTT connection using AWS SDK with correct certificate files
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=garage_config.IOT_ENDPOINT,
                cert_filepath='GarageController.cert.pem',
                pri_key_filepath='GarageController.private.key',
                ca_filepath='root-CA.crt',
                client_id='garage_simulator',
                clean_session=False,
                keep_alive_secs=30
            )

            # Set up callbacks with timeout
            connect_future = self.mqtt_connection.connect()
            connect_future.add_done_callback(self.on_aws_connection_result)

            print("AWS IoT connection initiated...")

            # Add connection timeout
            threading.Timer(10.0, self.check_connection_timeout).start()

        except Exception as e:
            print(f"AWS IoT SDK connection error: {e}")
            print("Falling back to paho-mqtt...")
            self.setup_paho_mqtt_connection()

    def check_connection_timeout(self):
        """Check if connection took too long and provide helpful message"""
        if not self.connected:
            print("⏱️ Connection taking longer than expected...")
            print("This usually indicates an AWS IoT policy or certificate issue.")
            print("Running in OFFLINE mode - manual controls still work!")
            print("\n🔧 To fix AWS IoT connection:")
            print("1. Check that your IoT Thing policy allows iot:Connect, iot:Publish, iot:Subscribe")
            print("2. Verify the certificate is attached to your Thing")
            print("3. Ensure your Thing name is 'GarageController'")
            print("4. Check AWS IoT logs in CloudWatch")

    def setup_paho_mqtt_connection(self):
        """Fallback to paho-mqtt with multiple SSL configurations"""
        try:
            # Validate certificate files exist with correct names
            cert_files = ['root-CA.crt', 'GarageController.cert.pem', 'GarageController.private.key']
            for cert_file in cert_files:
                if not os.path.exists(cert_file):
                    print(f"Error: Certificate file {cert_file} not found!")
                    print("Running in offline mode - simulator will not receive real-time updates")
                    return

            print("Setting up paho-mqtt connection...")

            # MQTT setup using older compatible API
            self.client = mqtt.Client(client_id="garage_simulator")
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.on_disconnect = self.on_disconnect

            # Try multiple SSL configurations with correct certificate files
            ssl_configs = [
                # Config 1: Basic SSL with insecure mode
                {
                    "name": "Basic SSL with insecure mode",
                    "config": lambda: (
                        self.client.tls_set(
                            ca_certs='root-CA.crt',
                            certfile='GarageController.cert.pem',
                            keyfile='GarageController.private.key'
                        ),
                        self.client.tls_insecure_set(True)
                    )
                },
                # Config 2: SSL with specific protocol version
                {
                    "name": "SSL with TLS v1.2",
                    "config": lambda: self.client.tls_set(
                        ca_certs='root-CA.crt',
                        certfile='GarageController.cert.pem',
                        keyfile='GarageController.private.key',
                        cert_reqs=ssl.CERT_REQUIRED,
                        tls_version=ssl.PROTOCOL_TLSv1_2
                    )
                }
            ]

            for ssl_config in ssl_configs:
                try:
                    print(f"Trying {ssl_config['name']}...")
                    ssl_config['config']()

                    # Connect to IoT endpoint
                    print(f"Connecting to AWS IoT endpoint: {garage_config.IOT_ENDPOINT}")
                    self.client.connect(garage_config.IOT_ENDPOINT, 8883, 60)

                    # Start MQTT loop in separate thread
                    self.client.loop_start()
                    print("Paho-MQTT connection initiated...")
                    return  # Success, exit the loop

                except Exception as e:
                    print(f"SSL config '{ssl_config['name']}' failed: {e}")
                    continue

            print("All SSL configurations failed. Running in offline mode.")

        except Exception as e:
            print(f"MQTT connection error: {e}")
            print("Running in offline mode - simulator will not receive real-time updates")

    def on_aws_connection_result(self, connect_future):
        """Callback for AWS IoT SDK connection result"""
        try:
            connect_future.result()
            print("✅ AWS IoT connection successful!")
            self.connected = True

            # Subscribe to garage state topic
            subscribe_future, packet_id = self.mqtt_connection.subscribe(
                topic="garage/state",
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=self.on_aws_message_received
            )
            print("Subscribed to garage/state topic")

        except Exception as e:
            print(f"AWS IoT connection failed: {e}")
            print("Falling back to paho-mqtt...")
            self.connected = False
            self.setup_paho_mqtt_connection()

    def on_aws_message_received(self, topic, payload, **kwargs):
        """Handle AWS IoT SDK messages"""
        try:
            message = json.loads(payload.decode())
            self.process_message(message)
        except Exception as e:
            print(f"Error processing AWS IoT message: {e}")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for paho-mqtt connection"""
        if rc != 0:
            print(f"Failed to connect to AWS IoT. Return code: {rc}")
            self.connected = False
            return

        print("✅ Paho-MQTT connection successful!")
        self.connected = True
        client.subscribe("garage/state")
        print("Subscribed to garage/state topic")

    def on_disconnect(self, client, userdata, rc, properties=None):
        """Callback for paho-mqtt disconnection"""
        if rc == 0:
            print("Disconnected normally from AWS IoT")
        else:
            print(f"Unexpected disconnection from AWS IoT (code: {rc})")
        self.connected = False

    def on_message(self, client, userdata, msg):
        """Handle paho-mqtt messages"""
        try:
            payload = json.loads(msg.payload.decode())
            self.process_message(payload)
        except Exception as e:
            print(f"Error processing paho-mqtt message: {e}")

    def process_message(self, payload):
        """Common message processing for both MQTT clients"""
        try:
            # Validate token for security
            if payload.get('token') != garage_config.SECRET_TOKEN:
                print("Invalid token in message - ignoring")
                return

            # Process state change
            if "state" in payload:
                new_state = (payload["state"] == "open")
                if new_state != self.door_open:
                    print(f"Changing door state from {self.door_open} to {new_state}")
                    self.door_open = new_state
            else:
                print("Warning: 'state' field missing in payload")

        except Exception as e:
            print(f"Error processing message: {e}")

    def draw_garage(self):
        """Draw the garage door simulation"""
        # Clear screen
        self.screen.fill((30, 30, 40))

        # Garage frame (outer structure)
        pygame.draw.rect(self.screen, (80, 80, 90), (150, 100, 300, 450), 0)
        pygame.draw.rect(self.screen, (60, 60, 70), (150, 100, 300, 450), 4)

        # Garage door (moves up when opening)
        door_color = (180, 190, 200) if self.door_open else (150, 160, 170)
        door_rect = pygame.Rect(160, 110 + self.door_height, 280, 400 - self.door_height)
        pygame.draw.rect(self.screen, door_color, door_rect, 0)
        pygame.draw.rect(self.screen, (100, 100, 110), door_rect, 2)

        # Door panels (visual detail)
        if self.door_height < 400:
            panel_height = max(20, (400 - self.door_height) // 5)
            for i in range(5):
                y_pos = 110 + self.door_height + (i * panel_height)
                if y_pos < 510:
                    pygame.draw.line(self.screen, (120, 130, 140),
                                     (170, y_pos), (430, y_pos), 3)

        # Door tracks (vertical guides)
        pygame.draw.rect(self.screen, (100, 100, 110), (150, 110, 10, 400), 0)
        pygame.draw.rect(self.screen, (100, 100, 110), (440, 110, 10, 400), 0)

        # Status panel
        pygame.draw.rect(self.screen, (40, 40, 50), (0, 0, 600, 80), 0)
        pygame.draw.line(self.screen, (70, 70, 80), (0, 80), (600, 80), 2)

        # Status text
        font = pygame.font.SysFont(None, 48)
        status = "OPEN" if self.door_open else "CLOSED"
        color = (50, 200, 50) if self.door_open else (220, 50, 50)
        text = font.render(f"GARAGE: {status}", True, color)
        self.screen.blit(text, (180, 20))

        # Connection status
        status_font = pygame.font.SysFont(None, 28)
        conn_status = "CONNECTED" if self.connected else "OFFLINE"
        conn_color = (50, 200, 50) if self.connected else (220, 50, 50)
        conn_text = status_font.render(f"MQTT: {conn_status}", True, conn_color)
        self.screen.blit(conn_text, (20, 20))

        # Instructions
        instr_font = pygame.font.SysFont(None, 24)
        instr_text = instr_font.render("Press O to Open, C to Close, ESC to Exit", True, (180, 180, 200))
        self.screen.blit(instr_text, (20, 50))

        # Door position indicator
        pos_text = status_font.render(f"Position: {400 - self.door_height}/400", True, (200, 200, 220))
        self.screen.blit(pos_text, (20, 550))

    def run(self):
        """Main simulation loop"""
        print("Starting Garage Door Simulator")
        print("Press O to Open, C to Close, ESC to exit")

        while self.running:
            current_time = time.time()
            delta_time = current_time - self.last_update_time
            self.last_update_time = current_time

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_o:
                        self.door_open = True
                        print("Manual command: OPEN")
                    elif event.key == pygame.K_c:
                        self.door_open = False
                        print("Manual command: CLOSE")

            # Smooth door animation with time-based movement
            target_height = 400 if self.door_open else 0
            movement = 200 * delta_time

            if self.door_height < target_height:
                self.door_height = min(self.door_height + movement, target_height)
            elif self.door_height > target_height:
                self.door_height = max(self.door_height - movement, target_height)

            # Draw everything
            self.draw_garage()
            pygame.display.flip()
            self.clock.tick(60)

        # Cleanup
        self.shutdown()

    def shutdown(self):
        """Clean shutdown of the simulator"""
        print("Shutting down garage simulator...")
        self.running = False

        try:
            if USE_AWS_SDK and hasattr(self, 'mqtt_connection') and self.connected:
                self.mqtt_connection.disconnect()
            elif hasattr(self, 'client'):
                if self.connected:
                    self.client.disconnect()
                self.client.loop_stop()
        except Exception as e:
            print(f"Error during MQTT cleanup: {e}")

        pygame.quit()
        print("Garage simulator shut down successfully")


if __name__ == "__main__":
    try:
        simulator = GarageSimulator()
        simulator.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error running simulator: {e}")
    finally:
        pygame.quit()
        sys.exit(0)
