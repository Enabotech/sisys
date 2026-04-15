Feature: Story 1.3 - Dual-Channel Event Bus Implementation
  As a system architect
  I want to implement a dual-channel event bus (Redis Pub/Sub + RabbitMQ + Outbox)
  So that system modules can communicate via standardized asynchronous events

  Background:
    Given Story 1.1 hexagonal architecture skeleton and Story 1.2 domain events are implemented

  @AC-1 @e2e
  Scenario Outline: AC-1 - Redis Pub/Sub real-time notification channel
    When I publish a <event_type> event to Redis channel
    Then the subscriber should receive the event
    And the event should be correctly serialized as JSON
    And the Redis channel name should follow sisys:rt:<event_type_lowercase> convention

    Examples:
      | event_type           | event_type_lowercase |
      | DocumentProcessed    | documentprocessed    |
      | HeartbeatTriggered   | heartbeattriggered   |

  @AC-2 @e2e
  Scenario Outline: AC-2 - RabbitMQ reliable event channel (async path)
    When I async publish a <event_type> event to RabbitMQ
    Then the async consumer should receive the event
    And the message should be persisted (durable=True, delivery_mode=2)
    And the routing key should follow sisys.events.reliable.<event_type> convention

    Examples:
      | event_type        |
      | DocumentProcessed |
      | AgentDecided      |

  @AC-3 @e2e
  Scenario Outline: AC-3 - Transaction Outbox Pattern
    When I save a <event_type> event to OutboxRepository
    Then the event should be stored with pending status
    And the AsyncOutboxPoller should pick up the event
    And the event should be published to RabbitMQ
    And the event status should be updated to published

    Examples:
      | event_type        |
      | DocumentProcessed |
      | ToolExecuted      |

  @AC-4.1 @e2e
  Scenario: AC-4.1 - Event processing idempotency check
    When I process an event with event_id "550e8400-e29b-41d4-a716-446655440000" for the first time
    Then try_acquire should return True
    Then I process the same event_id "550e8400-e29b-41d4-a716-446655440000" a second time
    And try_acquire should return False
    And the event should only be processed once

  @AC-4.2 @e2e
  Scenario: AC-4.2 - Event processing retry mechanism (exponential backoff + jitter)
    When event processing fails and triggers retry
    Then the retry delay should follow exponential backoff: min(base * 2^retry_count * jitter, max)
    And jitter should be between 0.5 and 1.5
    And the event should enter the dead letter queue after max retries exceeded

  @AC-5 @e2e
  Scenario: AC-5 - Event processing monitoring and observability
    When an event is successfully processed
    Then the events_processed_total counter should increment
    When an event processing fails
    Then the events_failed_total counter should increment
    And an OpenTelemetry span should be created when EVENT_BUS_OTEL_TRACE_ENABLED=true

  @AC-6 @e2e
  Scenario: AC-6 - Architecture constraint validation
    When I run architecture constraint validation tests
    Then the domain layer should not import OutboxEntity
    And Redis/RabbitMQ client imports should only be in infrastructure layer
    And Ruff check should pass (0 errors)
    And MyPy type check should pass (0 issues)
