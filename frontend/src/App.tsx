import { useChat } from "@ai-sdk/react";
import "./App.css";

function App() {
  const API_URL = "http://localhost:8000/chat";
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    keepLastMessageOnError: true,
    api: API_URL,
  });

  return (
    <>
      {messages.map((message) => (
        <div key={message.id}>
          {message.role === "user" ? "User: " : "AI: "}
          {message.content}
        </div>
      ))}

      <form onSubmit={handleSubmit}>
        <input name="prompt" value={input} onChange={handleInputChange} />
        <button type="submit">Submit</button>
      </form>
    </>
  );
}

export default App;
