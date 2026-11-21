package com.shop.payment_service.controller;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ChaosController {
    private static final Logger log = LoggerFactory.getLogger(ChaosController.class);
     static volatile int latencyMs = 0;
     static volatile boolean errorsOn = false;


     @PostMapping("/chaos/latency")
     public String latency(@RequestParam int ms){
        latencyMs = ms;
        log.warn("CHAOS: latency set to {}ms",ms);
        return "latency = " + ms + "ms";
     }

     @PostMapping("/chaos/errors")
     public String errors(@RequestParam boolean on){
        errorsOn = on;
        log.warn("CHAOS: errors set to {}", on);
        return "errors = " + on;
     }

    @PostMapping("/chaos/reset")
    public String reset() {
        latencyMs = 0;
        errorsOn = false;
        log.warn("CHAOS: reset, back to normal");
        return "reset";
    }
}
