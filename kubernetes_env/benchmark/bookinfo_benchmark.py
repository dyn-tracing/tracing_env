from locust import HttpUser, task, between, events
import locust
import time

class BookInfoUser(HttpUser):
    wait_time = between(1, 2)

    @task(1)
    def productpage(self):
        self.client.get("/productpage")

    @events.request.add_listener
    def on_request(request_type, name, response_time, response_length, response,
                       context, exception, **kwargs):
        start_time = time.time()-(response_time*1000) # seconds, not milliseconds, since the epoch
        print(f"{start_time}, {name}, {response_time}, {response.status_code}")
