# Physical Simulation (PyGame)

import pygame
import json
import paho.mqtt.client as mqtt
import threading
import garage_config


class GarageSimulator:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((600, 600))
        pygame.display.set_caption("Garage Door Simulator")
        self.clock = pygame.time.Clock()
        self.door_height = 0
        self.door_open = False

        # MQTT setup
        self.client = mqtt.Client(client_id="garage_simulator")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # TLS configuration for AWS IoT
        try:
            self.client.tls_set(
                ca_certs='root-CA.crt',
                certfile='certificate.pem.crt',
                keyfile='private.pem.key'
            )
            # Use IoT endpoint from configuration
            self.client.connect(garage_config.IOT_ENDPOINT, 8883)
            threading.Thread(target=self.client.loop_forever, daemon=True).start()
        except Exception as e:
            print(f"MQTT connection error: {e}")
            print("Running in offline mode - simulator will not receive real-time updates")

    def on_connect(self, client, userdata, flags, rc):
        print(f"Simulator connected to IoT with code {rc}")
        client.subscribe("garage/state")

    def on_message(self, client, userdata, msg):
        try:
            print(f"Received message on topic: {msg.topic}")
            payload_str = msg.payload.decode()
            print(f"Message payload: {payload_str}")

            payload = json.loads(payload_str)
            print(f"Parsed payload: {payload}")

            if "state" in payload:
                new_state = (payload["state"] == "open")
                print(f"Changing door state from {self.door_open} to {new_state}")
                self.door_open = new_state
            else:
                print("Error: 'state' field missing in payload")
        except Exception as e:
            print(f"Error processing message: {e}")

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Update door position
            if self.door_open and self.door_height < 400:
                self.door_height += 5
            elif not self.door_open and self.door_height > 0:
                self.door_height -= 5

            # Draw garage
            self.screen.fill((50, 50, 50))

            # Garage frame
            pygame.draw.rect(self.screen, (100, 100, 100), (150, 100, 300, 450), 0)

            # Garage door
            pygame.draw.rect(self.screen, (200, 200, 200), (170, 120, 260, 400 - self.door_height), 0)

            # Door tracks
            pygame.draw.rect(self.screen, (150, 150, 150), (160, 120, 10, 400), 0)
            pygame.draw.rect(self.screen, (150, 150, 150), (430, 120, 10, 400), 0)

            # Status text
            font = pygame.font.SysFont(None, 48)
            status = "OPEN" if self.door_open else "CLOSED"
            color = (0, 255, 0) if self.door_open else (255, 0, 0)
            text = font.render(f"GARAGE: {status}", True, color)
            self.screen.blit(text, (150, 30))

            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()


if __name__ == "__main__":
    simulator = GarageSimulator()
    simulator.run()
