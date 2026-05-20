local key = KEYS[1]

local capacity = tonumber(ARGV[1])
local refillRate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local tokensNeeded = tonumber(ARGV[4]) or 1

local tokenField = 'tokens'
local timestampField = 'timestamp'

local state = redis.call('HMGET', key, tokenField, timestampField)
local tokens = tonumber(state[1])
local lastRefill = tonumber(state[2])

if tokens == nil then
    tokens = capacity
    lastRefill = now
else
    local elapsed = math.max(0, now - lastRefill)
    local refill = elapsed * refillRate
    tokens = math.min(capacity, tokens + refill)
    lastRefill = now
end

if tokens < tokensNeeded then
    redis.call('HMSET', key, tokenField, tokens, timestampField, lastRefill)
    return 0
end

tokens = tokens - tokensNeeded
redis.call('HMSET', key, tokenField, tokens, timestampField, lastRefill)
return 1
