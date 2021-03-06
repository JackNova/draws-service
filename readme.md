[![Build Status](https://drone.io/github.com/JackNova/draws-service/status.png)](https://drone.io/github.com/JackNova/draws-service/latest)
[![Coverage Status](https://coveralls.io/repos/github/JackNova/draws-service/badge.svg?branch=master)](https://coveralls.io/github/JackNova/draws-service?branch=master)

# OBJECTIVE

The objective of this simple project has been / is to experiment with a particular development approach better described following.
I decided to follow and extract some principles of various kind in order to be consistent with them and avoid wastring time in decisions that add little business value.

# THE TASK

There is a particular kind of lottery in Italy where they draw numbers every 5 minutes, giving you 288 draws each day. (8928 draws in a month of 31 days).
Only the first year of draws is available online for you to check it.
I'd like to have my own copy of their repo with the draws.

- Design a cron job that will keep my repo in sync
- Whenever the synchronization starts, download all the available draws (past)
- Do not download the same draw multiple times
- The entire operation should be idempotent
- Have control of the frequency of the http requests that are made in order to synchronize my system
- Don't issue more than a request every 10 seconds in order to not overload the third party system
- Have a retry/fall-back policy for the requests
- Capture requests that fail permanently in a Hospital where I can inspect them manually
- Have an health monitoring system that notifies me by email when something goes wrong
- Have 100% coverage of the application
- Expect the need to do real-time statistics on data you collect
- Try to generalize the entire operation so that can be applied to a different task just providing a set of adapters
- Abstract out the infrastructure


# PRINCIPLES I FOLLOWED

## APPENGINE

### TASKQUEUE ORGANIZATION

taskqueue are powerful tools, they give you retry/back-off policy for free and allow you a fine grained configuration on the queue behaviour.

- put directly in the index of your module the EventHandlers that are just wrapper for a taskqueue call. This way you have complete visibility on the urls that compose the module.

## DESIGN

### WISHFUL THINKING

When starting the design of your system, provide a natural language description of the task that you are trying to accomplish and make use of an ideal module called wish that contains all of the operations you need to orchestrate in order to accomplish your task.

- strive to keep optimization details out of this layer of code
- start implementing the operations you wish you had keeping in mind that you have to split and arrange them in order to have useful and meaningful tests assuring you the good health of your code base
- when the application is complete and works and your coverage is near 100% and all tests pass, start organizing the taxonomy of your system, getting rid of the only wish module, make use of dependency injection

### ABSTRACT AWAY THE INFRASTRUCTURE

Avoid tight coupling of infrastructure specific details with your codebase

### KEEP AWAY FROM FUNCTIONAL DECOMPOSITION

Remember that the functionality of your application should came out of orchestration of other components.
Have your taxonomy composed of Managers that are composed of Engines

### ENCAPSULATE THIRD PARTY SYSTEMS CALLS DETAILS

encapsulate details of http request towards third parties: have a function that knows about the details of the request/response and have a function that uses this http client and formats/outputs the data in a format that makes sense for the rest of the application.


### BALANCE UNIVERSAL PRINCIPLES WITH PRAGMATIC NEEDS

when designing the system avoid putting to much effort on the quest for the Graal and start from your pragmatic needs instead


### REPOSITORY

I prefer a top bottom design: first I choose what is the api that I need in my application (this is obvious if you follow a wishful thinking approach, layers and taxonomy doesn't exist yet when the first working version of the core functionality of the application is delivered).

Domain entities should be represented as immutable data structure and should contain no logic, when working with python my choice is named tuples.

The fact that you will use data in a certain way and making use of particular data structure shouldn't go into the repository but should live at logic level: in this particular application, one of the requirement of the application is to be able to check if a particular draw has already been downloaded; since there is a moment when the application does many of this calls one after the other, I choose to benefit of the `set` characteristics and make a set of tuples that I can quickly query with the pattern `some_draw in draws_tuples_set`.
In the first draft of the application I was returning that kind of set from the functions in the wish module. Then I re-factored promoting a more general and simple api for the repository.

There are 3 layers of responsibility:
- the business logic layer, here you make use of the public api of the repository module, here you shape the aspect of the api; apply particular transformation to the retrieved data to reach particular goals; make use of custom data structures.
- the repository interface (the public api you will expose). Here you should exchange information using primitive types and domain entities; this layer is a wrapper on the underlying one that encapsulate infrastructure specific concepts.
- closer to the infrastructure details: here I use the ndb library and encapsulate all that is tightly coupled with the library and the infrastructure: querying, sorting, data modeling.


## TESTING

### TEST PYRAMID

Have the most of your tests composed of unit tests, write them first. As soon as you have all of the operations you need to orchestrate to offer a funcionality write the integration tests.

### NO LOGS IN TESTS

- survive the temptation of logging when test results are not what you expect, write more and better unit tests to diagnose and fix the problem

### CONTINUOUS INTEGRATION

- choose the environment where you will run your continuous integration pipeline early and strieve to replicate the exact same environment on your machine.

### WRITE TESTS BEFORE FIXING BUGS

whenever you notice a bug, your first task should be write the test that captures that bug, then refactor and ensure that the test passes.

# ENSURING IDEMPOTENCY AND DETERMINISM

- Use a custom queue to schedule the `download-all` task to ensure that only one task at a time in that queue gets executed, it will be impossible to schedule other tasks when one is in progress
- The first operation of that task is to check a flag into memcache that tells if the download-all operation is in progress, if not set it, if yes stop immediately
- Enqueue the first cluster of operation (one day draws for example)

