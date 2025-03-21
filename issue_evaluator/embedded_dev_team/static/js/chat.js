document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const issueSelector = document.getElementById('issue-selector');
    
    // Load the first issue by default
    if (issueSelector && issueSelector.value) {
        loadIssue(issueSelector.value);
    }
    
    // Handle issue selection change
    if (issueSelector) {
        issueSelector.addEventListener('change', function() {
            loadIssue(this.value);
        });
    }
    
    // Handle chat form submission
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const message = chatInput.value.trim();
            const evaluation = document.getElementById('evaluation-criteria').value.trim();
            if (message) {
                // Add user message to chat
                addMessage(message, 'user');
                
                // Clear input field
                chatInput.value = '';
                
                // Get current issue ID
                const issueId = issueSelector.value;
                
                // Send message to backend
                sendMessage(message, evaluation, issueId);
            }
        });
    }
    // Function to show the typing indicator
    function showTypingIndicator() {
        // Remove any existing indicator first (just to be safe)
        hideTypingIndicator();
        
        // Create the typing indicator element
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        typingIndicator.id = 'typing-indicator';
        typingIndicator.style.display = 'block';
  
        // Add the dots
        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('span');
            typingIndicator.appendChild(dot);
        }
        
        // Append to chat-messages
        const chatMessages = document.querySelector('.chat-messages');
        chatMessages.appendChild(typingIndicator);
        
        // Scroll to the bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Function to hide the typing indicator
    function hideTypingIndicator() {
        const existingIndicator = document.getElementById('typing-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }
    }

    // Function to load issue details
    function loadIssue(issueId) {
        fetch(`/api/issues/${issueId}`)
            .then(response => response.json())
            .then(data => {
                console.log("Loaded issue data:", data);
                
                // Update issue display
                document.getElementById('issue-title').textContent = data.title || "No Title";
                document.getElementById('issue-id').textContent = data.id || "-";
                document.getElementById('issue-status').textContent = data.status || "Unknown";
                document.getElementById('issue-created').textContent = data.created || "Unknown";
                
                // Format description as JSON if it's a JSON object or string
                const descriptionContainer = document.getElementById('issue-description');
                
                // Clear previous content
                descriptionContainer.innerHTML = '';
                
                // Check if description exists and is not empty
                if (data.description) {
                    console.log("Description type:", typeof data.description);
                    
                    let jsonData;
                    
                    // If description is a string that looks like JSON, try to parse it
                    if (typeof data.description === 'string') {
                        try {
                            jsonData = JSON.parse(data.description);
                            console.log("Parsed JSON data:", jsonData);
                        } catch (e) {
                            // If parsing fails, use the string as is
                            console.log("Failed to parse description as JSON:", e);
                            jsonData = data.description;
                        }
                    } else {
                        // If it's already an object, use it directly
                        console.log("Description is already an object");
                        jsonData = data.description;
                    }
                    
                    // If we have a valid object or array (not a primitive), format it as JSON
                    if (typeof jsonData === 'object' && jsonData !== null) {
                        console.log("Formatting as JSON object");
                        
                        // Use our JSON formatter to create collapsible JSON
                        parseAndFormatJSON(JSON.stringify(jsonData), descriptionContainer);
                    } else {
                        // For primitive values or parsing failures, display as plain text
                        console.log("Displaying as plain text");
                        descriptionContainer.textContent = data.description;
                    }
                } else {
                    descriptionContainer.textContent = "No description available";
                }
                
                // Clear previous comments
                const commentsContainer = document.getElementById('issue-comments');
                commentsContainer.innerHTML = '';
                
                // Add comments if any
                if (data.comments && data.comments.length > 0) {
                    data.comments.forEach(comment => {
                        const commentElement = document.createElement('div');
                        commentElement.className = 'comment';
                        commentElement.innerHTML = `
                            <div class="comment-author">${comment.author}</div>
                            <div class="comment-date">${comment.date}</div>
                            <div class="comment-content">${comment.content}</div>
                        `;
                        commentsContainer.appendChild(commentElement);
                    });
                } else {
                    commentsContainer.innerHTML = '<p>No comments yet.</p>';
                }
                
                // Clear chat messages when switching issues
                chatMessages.innerHTML = '';
                
                // Add a welcome message from the AI
                addMessage(`I'm here to help with issue ${data.id}: ${data.title}. What would you like to know?`, 'ai');
            })
            .catch(error => {
                console.error('Error loading issue:', error);
                const issueContent = document.getElementById('issue-content');
                if (issueContent) {
                    issueContent.innerHTML = '<p>Error loading issue. Please try again.</p>';
                }
            });
    }
    
    // Function to format JSON with syntax highlighting
    function formatJsonSyntax(json) {
        // Replace with HTML for syntax highlighting
        return json
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
                let cls = 'json-number';
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'json-key';
                    } else {
                        cls = 'json-string';
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'json-boolean';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return '<span class="' + cls + '">' + match + '</span>';
            });
    }
    
    
    // Function to add a message to the chat
    function addMessage(text, sender) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}-message`;
        
        // Check if the message is a JSON string
        try {
            const jsonData = JSON.parse(text);
            // If parsing succeeds, format it as collapsible JSON
            const jsonContainer = document.createElement('div');
            parseAndFormatJSON(text, jsonContainer);
            messageElement.appendChild(jsonContainer);
        } catch (e) {
            // If not JSON, display as regular text
            messageElement.textContent = text;
        }
        
        chatMessages.appendChild(messageElement);
        
        // Scroll to the bottom of the chat
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to send message to backend
    function sendMessage(message, evaluation, issueId) {
        showTypingIndicator();
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                evaluation: evaluation,
                issue_id: issueId
            }),
        })
        .then(response => response.json())
        .then(data => {
            hideTypingIndicator();
            // Add AI response to chat
            addMessage(data.response, 'ai');
        })
        .catch(error => {
            console.error('Error sending message:', error);
            hideTypingIndicator();
            addMessage('Sorry, there was an error processing your request.', 'ai');
        });
    }
});