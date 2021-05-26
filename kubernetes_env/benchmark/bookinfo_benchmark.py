from locust import HttpUser, task, between

class BookInfoUser(HttpUser):
    wait_time = between(5, 15)

    @task(1)
    def productpage(self):
        self.client.get("/productpage")
