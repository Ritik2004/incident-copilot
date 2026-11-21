package com.shop.payment_service.controller;

import java.util.Map;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestParam;


@RestController
public class Paymentcontroller {
    
    
    private static final Logger log = LoggerFactory.getLogger(Paymentcontroller.class);
    @PostMapping("/payments")
    public Map<String, String> completeOrder(@RequestParam String orderid) throws InterruptedException{

        if (ChaosController.latencyMs > 0) {
    Thread.sleep(ChaosController.latencyMs);       // be slow
}
if (ChaosController.errorsOn) {
    log.error("Payment gateway failure for order {}", orderid);
    throw new RuntimeException("Payment gateway failure");   // fail → 500
}
        log.info("Payment processed for order {}", orderid);
        return Map.of("orderId",orderid,"status","PAID");
    }
    

}
