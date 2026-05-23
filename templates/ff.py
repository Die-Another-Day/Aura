import google.generativeai as genai

genai.configure(api_key="AIzaSyDBiEedMVBiLmIqSJM2lj0bA1cp6dU1e4g")

# model = genai.GenerativeModel("gemini-2.0-flash")
# model = genai.GenerativeModel("gemini-1.5-flash")
model = genai.GenerativeModel("gemini-2.5-flash")

response = model.generate_content("Hello")

print(response.text)
