# Prodigal Payment Collection Agent

An intelligent, conversational AI agent designed to guide users through an end-to-end payment collection flow. It handles unstructured natural language, enforces strict business rules, securely validates identity, and processes card payments via a simulated API.

## Features
- **Conversational NLU**: Built on **Google `gemini-3.1-flash-lite`**. This specific lightweight model was chosen due to its higher rate limits on the free tier, which enabled us to run our rigorous automated evaluation suite across many test cases without hitting quota limits. While it performs exceptionally well on messy, out-of-order inputs (e.g., "my acc is 1 0 0 1"), the agent's reasoning performance and robustness will scale even higher when plugged into a more powerful model like Gemini 3.1 Pro or GPT-4o.
- **Strict Verification**: Enforces exact name matching + 1 secondary factor (DOB, Aadhaar last 4, or pincode) before allowing any payment attempts.
- **Pre-API Validation**: Uses local Python validators (Luhn check, expiry check) to validate card formats *before* hitting the payment API, saving latency.
- **Graceful Failure Handling**: Differentiates between User Errors (wrong CVV) and System Errors (API timeouts). Implements exponential backoff via `tenacity`.
- **Zero Data Leakage**: Sensitive data retrieved from the backend is stored in a secure session state and *never* injected into the LLM prompt.

## Setup Instructions

1. **Clone the repository and enter the directory**
   ```bash
   git clone <repo-url>
   cd Prodigal
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv agent-env
   # On Windows:
   source agent-env/Scripts/activate
   # On macOS/Linux:
   source agent-env/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   Create a `.env` file in the root directory and add your Google API key:
   ```env
   GOOGLE_API_KEY="your_api_key_here"
   ```

## Run Instructions

### 1. Interactive CLI (Manual Testing)
Run the agent in an interactive chat loop. The interface exposes the exact `agent.next()` contract required by the specification.
```bash
python run.py
```
*Type `quit` or `exit` to end the session.*

### 2. Automated Evaluator
Run the built-in evaluation suite. This tests 13 distinct user personas (Happy path, messy NLP, leap year dates, validation failures) and outputs a detailed metrics summary.
```bash
python -m eval.evaluator
```

## Automated Evaluation Results

The agent includes a rigorous automated test suite that validates deterministic behavior, API error handling, and zero data leakage. 

```text
======================================================================
  Payment Agent — Automated Evaluation
======================================================================

Running: happy_path_dob — Full successful flow — ACC1001, verify via DOB
  [PASS] Turns: 8/8

Running: happy_path_aadhaar_partial — Verify via Aadhaar last 4, partial payment of ₹500
  [PASS] Turns: 6/6

Running: account_not_found — Non-existent account ID
  [PASS] Turns: 2/2

Running: verification_wrong_name_exhausted — Wrong name 3 times → session terminated
  [PASS] Turns: 5/5

Running: verification_succeeds_on_retry — Wrong secondary factor once, correct on retry
  [PASS] Turns: 5/5

Running: payment_invalid_card_luhn — Card fails Luhn check — pre-validation catches it
  [PASS] Turns: 6/6

Running: payment_insufficient_balance — Amount exceeds balance
  [PASS] Turns: 5/5

Running: zero_balance_account — ACC1003 has ₹0 balance — agent should surface this
  [PASS] Turns: 4/4

Running: leap_year_dob_valid — ACC1004 — DOB 1988-02-29 is a real leap year
  [PASS] Turns: 4/4

Running: messy_nlp_parsing — Out of order name, natural language dates, spacing in card
  [PASS] Turns: 5/5

======================================================================
  Metrics Summary
======================================================================
  Test cases passed   : 10/10 (100%)
  Turn-level pass rate: 100.0%
  Sensitive leakage   : 0 case(s)

  Happy Path                  : 2/2
  Verification Failures       : 2/2
  Payment Failures            : 2/2
  Messy NL / Edge Cases       : 4/4
======================================================================
```

---

## Sample Conversations (Real Test Runs)

### 1. Successful End-to-End Payment (Messy Inputs)
```text
Agent: Hello! Thank you for reaching out to us. I'm here to help you with your payment today.
To get started, could you please provide your account ID?

You: Hi, my Account id is acc 1001

Agent: Thank you. I have successfully located your account. To proceed with the next steps, could you please provide your full name? Also, to verify your identity, would you be able to provide either your date of birth, the last 4 digits of your Aadhaar card, or your pincode?

You: My name is Nithin Jain

Agent: Thank you, Nithin. Could you please verify your identity with your date of birth, the last 4 digits of your Aadhaar card, or your pincode?

You: sure, my DOB is 14th may 1990

Agent: Great! Thank you for that information, Nithin. Your identity has been successfully verified.
Your current outstanding balance is ₹1,250.75. How much would you like to pay today?

You: 500 is fine

Agent: Understood, a payment of ₹500.00.
To process this payment, I'll need your card details:
- Cardholder name
- Expiry date (month and year)
- CVV

You: sure, cardholder name is Nithin Jain, card number is 4532015112830366, cvv is 123, expiry 12, 27

Agent: Thank you, Nithin. Your payment of ₹500.00 has been successfully processed. Your transaction ID is txn_1779080155407_ij54vk6.
It was a pleasure assisting you today. If you need anything else, feel free to reach out. Have a wonderful day!
```

### 2. Pay 0 / Zero Payment Request
```text
Agent: Hello! I'm here to help you with your payment today. Could you please provide your account ID so I can get started?

You: hi, my account id is ACC 1002

Agent: Thank you. I have successfully located your account. To proceed, could you please provide your full name?
Also, to verify your identity, could you please share your date of birth, the last 4 digits of your Aadhaar card, or your pincode?

You: hi my name is Rajarajeswari Balasubramaniam

Agent: Thank you, Rajarajeswari. Could you also verify your identity with your date of birth, the last 4 digits of your Aadhaar card, or your pincode?

You: last 4 digits of aadhar are 9876

Agent: Thank you, Rajarajeswari. Your identity has been successfully verified.
Your current outstanding balance is ₹540.00. How much would you like to pay today?

You: I would like to pay 0

Agent: I understand you'd like to pay ₹0 today. Since there is no payment to process, I will go ahead and close this session for you.
If you decide you would like to make a payment later or if you need any other assistance, please feel free to reach out again. Thank you and have a wonderful day!
```

### 3. Zero Balance Account Verification Failure Recovery
```text
Agent: Hello! Thank you for reaching out to us today. I would be happy to help you with your payment.
To get started, could you please provide your account ID?

You: hi account id is acc 1003

Agent: Thank you. I have successfully located your account. To proceed with the verification process, could you please provide your full name?
Additionally, for security purposes, could you verify your identity with one of the following: your date of birth, the last 4 digits of your Aadhaar card, or your pincode?

You: It's Priya Agarwal

Agent: Thank you, Priya. To complete the verification, please provide one of the following: your date of birth, the last 4 digits of your Aadhaar card, or your pincode.

You: my pincode is 400001

Agent: I've checked the information provided, but it doesn't match our records. I checked your pincode as 400001 — is that correct?
If not, please double-check the pincode, or you may try using your date of birth (in DD-MM-YYYY format) or the last 4 digits of your Aadhaar card instead.

You: ok ill provide my dob 10th august 1992

Agent: Thank you, Priya. Your identity has been successfully verified.
Your current outstanding balance is ₹0.00. Since your balance is clear, there is no payment due at this time. Is there anything else I can assist you with today?
```
