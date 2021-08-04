# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import random
from locust import HttpUser, TaskSet, between, events
import time
import csv

wait_time = 1
start_time = 0
stats = []
products = [
    '0PUK6V6EV0',
    '1YMWWN1N4O',
    '2ZYFJ3GM2N',
    '66VCHSJNUP',
    '6E92ZMYYFZ',
    '9SIQT8TOJO',
    'L9ECAV7KIM',
    'LS4PSXUNUM',
    'OLJCESPC7Z']

def index(l):
    l.client.get("/", context={"request_start_time": time.time()})

def setCurrency(l):
    currencies = ['EUR', 'USD', 'JPY', 'CAD']
    l.client.post("/setCurrency",
        {'currency_code': random.choice(currencies)},
        context={"request_start_time": time.time()})

def browseProduct(l):
    l.client.get("/product/" + random.choice(products), context={"request_start_time": time.time()})

def viewCart(l):
    l.client.get("/cart", context={"request_start_time": time.time()})

def addToCart(l):
    product = random.choice(products)
    l.client.get("/product/" + product, context={"request_start_time": time.time()})
    l.client.post("/cart", {
        'product_id': product,
        'quantity': random.choice([1,2,3,4,5,10])},
    context={"request_start_time": time.time()})

def checkout(l):
    addToCart(l)
    l.client.post("/cart/checkout", {
        'email': 'someone@example.com',
        'street_address': '1600 Amphitheatre Parkway',
        'zip_code': '94043',
        'city': 'Mountain View',
        'state': 'CA',
        'country': 'United States',
        'credit_card_number': '4432-8015-6152-0454',
        'credit_card_expiration_month': '1',
        'credit_card_expiration_year': '2039',
        'credit_card_cvv': '672',
    }, context={"request_start_time": time.time()})

class UserBehavior(TaskSet):

    def on_start(self):
        index(self)

    tasks = {index: 1,
        setCurrency: 2,
        browseProduct: 10,
        addToCart: 2,
        viewCart: 3,
        checkout: 1}

class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 3)

@events.request.add_listener                                                    
def on_request(request_type, name, response_time, response_length, response,    
                   context, exception, **kwargs):                               
    global stats
    stats.append(["something"])
    if start_time != 0 and time.time() > start_time:                            
        request_start_time = context["request_start_time"]                      
        stats.append([request_start_time, name, response_time, response.status_code])
                                                                                
@events.spawning_complete.add_listener                                          
def set_recording_time(user_count, **kwargs):                                   
    global start_time                                                           
    stats.append(["something2"])
    start_time = time.time() + wait_time # start recording stats at wait_time after Locust is fully running
                                                                                
@events.quitting.add_listener                                                   
def write_to_csv(environment, **kwargs):                                        
    global stats
    with open("online_boutique_benchmark_results.csv", "a+") as csvfile:               
        csvwriter = csv.writer(csvfile)                                         
        for row in stats:                                                       
            csvwriter.writerow(row)  
