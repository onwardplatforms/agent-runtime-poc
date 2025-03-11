using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Azure.AI.OpenAI;
using DotNetEnv;

// Load .env file
Env.Load();

var builder = WebApplication.CreateBuilder(args);

// Configure logging
builder.Logging.ClearProviders();
builder.Logging.AddConsole();

if (args.Contains("--verbose") || args.Contains("-v"))
{
    builder.Logging.SetMinimumLevel(LogLevel.Information);
}
else
{
    builder.Logging.SetMinimumLevel(LogLevel.Warning);
}

// Add OpenAI client
var apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");
if (string.IsNullOrEmpty(apiKey))
{
    Console.WriteLine("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.");
    Environment.Exit(1);
}

builder.Services.AddSingleton(new OpenAIClient(apiKey));

// Add services
builder.Services.AddHttpClient();
builder.Services.AddSingleton<GoodbyeAgent>();

var app = builder.Build();

// Configure the HTTP request pipeline
app.MapPost("/api/message", async (HttpContext context, GoodbyeAgent agent) =>
{
    try
    {
        // Read the message from the request body
        var message = await context.Request.ReadFromJsonAsync<Message>();
        if (message == null)
        {
            context.Response.StatusCode = 400;
            await context.Response.WriteAsJsonAsync(new { error = "Invalid message format" });
            return;
        }
        
        // Process the message
        var responseContent = await agent.ProcessMessageAsync(message);
        
        // Create response message
        var response = new Message
        {
            MessageId = Guid.NewGuid().ToString(),
            ConversationId = message.ConversationId,
            SenderId = agent.AgentId,
            RecipientId = message.SenderId,
            Content = responseContent,
            Timestamp = DateTime.UtcNow,
            Type = MessageType.Text
        };
        
        // Return the response directly to the caller
        context.Response.StatusCode = 200;
        await context.Response.WriteAsJsonAsync(response);
    }
    catch (Exception ex)
    {
        var logger = context.RequestServices.GetRequiredService<ILogger<Program>>();
        logger.LogError(ex, "Error processing message");
        context.Response.StatusCode = 500;
        await context.Response.WriteAsJsonAsync(new { error = ex.Message });
    }
});

app.Run("http://localhost:5002");

// Goodbye Agent implementation
public class GoodbyeAgent
{
    private readonly HttpClient _httpClient;
    private readonly OpenAIClient _openAIClient;
    private readonly ILogger<GoodbyeAgent> _logger;
    
    // Fixed ID to match configuration in agents.json
    public string AgentId { get; } = "goodbye-agent";

    public GoodbyeAgent(IHttpClientFactory httpClientFactory, OpenAIClient openAIClient, ILogger<GoodbyeAgent> logger)
    {
        _httpClient = httpClientFactory.CreateClient();
        _openAIClient = openAIClient;
        _logger = logger;
        
        _logger.LogInformation($"Goodbye Agent initialized with ID: {AgentId}");
    }

    public async Task<string> ProcessMessageAsync(Message message)
    {
        try
        {
            _logger.LogInformation($"Processing message: {message.MessageId} from {message.SenderId}");
            
            string content = message.Content.ToLower();
            
            // Check if this is a farewell request
            if (content.Contains("goodbye") || content.Contains("bye") || content.Contains("farewell") || content.Contains("adios") || content.Contains("ciao"))
            {
                // Extract language if specified
                string language = "English"; // Default
                
                if (content.Contains("french"))
                    language = "French";
                else if (content.Contains("spanish"))
                    language = "Spanish";
                else if (content.Contains("german"))
                    language = "German";
                else if (content.Contains("italian"))
                    language = "Italian";
                else if (content.Contains("japanese"))
                    language = "Japanese";
                else if (content.Contains("chinese"))
                    language = "Chinese";
                
                // Generate the goodbye message
                string response = await GenerateGoodbyeAsync(language);
                
                _logger.LogInformation($"Generated response in {language}: {response}");
                return response;
            }
            
            // Default response for unrelated queries
            return "Goodbye Agent: I can help you say goodbye in different languages. Try asking me to say goodbye in a specific language.";
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing message");
            return "Sorry, I couldn't process your request at this time.";
        }
    }

    private async Task<string> GenerateGoodbyeAsync(string language)
    {
        try
        {
            var chatCompletionsOptions = new ChatCompletionsOptions
            {
                Messages = {
                    new ChatMessage(ChatRole.System, "You are a helpful assistant that generates farewell messages in different languages."),
                    new ChatMessage(ChatRole.User, $"Generate a friendly goodbye message in {language}. Keep it short and just the farewell text, no explanations.")
                },
                MaxTokens = 50
            };
            
            var response = await _openAIClient.GetChatCompletionsAsync("gpt-3.5-turbo", chatCompletionsOptions);
            var responseText = response.Value.Choices[0].Message.Content;
            
            return responseText?.Trim() ?? $"Goodbye! (in {language})";
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error generating goodbye message");
            return $"Goodbye! (Sorry, I had trouble with {language})";
        }
    }
}

// Message model to match the runtime's schema
public class Message
{
    public string MessageId { get; set; } = Guid.NewGuid().ToString();
    public string ConversationId { get; set; } = string.Empty;
    public string SenderId { get; set; } = string.Empty;
    public string RecipientId { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public bool Processed { get; set; } = false;
    public MessageType Type { get; set; } = MessageType.Text;
}

public enum MessageType
{
    Text,
    Command,
    Result,
    Error,
    System
} 