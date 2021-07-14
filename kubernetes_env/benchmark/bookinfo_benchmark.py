from locust import HttpUser, task, between, events
import locust
import time
import csv

wait_time = 1
start_time = 0
stats = []

class BookInfoUser(HttpUser):
    wait_time = between(1, 2)

    @task(1)
    def productpage(self):
        self.client.get("/productpage", context={"request_start_time": time.time()})

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response,
                   context, exception, **kwargs):
    if start_time != 0 and time.time() > start_time:
        request_start_time = context["request_start_time"]
        stats.append([request_start_time, name, response_time, response.status_code])

@events.spawning_complete.add_listener
def set_recording_time(user_count, **kwargs):
    global start_time
    start_time = time.time() + wait_time # start recording stats at wait_time after Locust is fully running

@events.quitting.add_listener
def write_to_csv(environment, **kwargs):
    with open("bookinfo_benchmark_results.csv", "a+") as csvfile:
        csvwriter = csv.writer(csvfile)
        for row in stats:
            csvwriter.writerow(row)
            
