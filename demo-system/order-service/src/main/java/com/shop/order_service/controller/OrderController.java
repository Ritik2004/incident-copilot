package com.shop.order_service.controller;

import java.util.Map;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.client.RestClient;

@RestController
public class OrderController{
    private final StringRedisTemplate redistemplate;
    OrderController(StringRedisTemplate redistemplate){
          this.redistemplate = redistemplate;
    }
    private static final Logger log = LoggerFactory.getLogger(OrderController.class);
    private final RestClient paymentClient = RestClient.create("http://payment-service:8080");
    

@PostMapping("/orders")
public Map<String,String> sendOrder(){
    String orderId = UUID.randomUUID().toString();
    redistemplate.opsForValue().set("order:" + orderId, "CREATED");

    Map<?,?>payment = paymentClient.post()
    .uri("/payments?orderid={id}",orderId)
    .retrieve().body(Map.class);

    log.info("Order created: {}", orderId);
    return Map.of("orderId", orderId, "status", (String) payment.get("status")); 
}
}
