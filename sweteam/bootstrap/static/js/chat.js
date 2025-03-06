document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const issueSelector = document.getElementById('issue-selector');
    
    // Load the first issue by default
    loadIssue(issueSelector.value);
    
    // Handle issue selection change
    issueSelector.addEventListener('change', function() {
        loadIssue(this.value);
    });
    
    // Handle chat form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (message) {
            // Add user message to chat
            addMessage(message, 'user');
            
            // Clear input field
            chatInput.value = '';
            
            // Get current issue ID
            const issueId = issueSelector.value;
            
            // Send message to backend
            sendMessage(message, issueId);
        }
    });
    
    // Function to load issue details
    function loadIssue(issueId) {
        fetch(`/api/issues/${issueId}`)
            .then(response => response.json())
            .then(data => {
                // Update issue display
                document.getElementById('issue-title').textContent = data.title;
                document.getElementById('issue-id').textContent = data.id;
                document.getElementById('issue-status').textContent = data.status;
                document.getElementById('issue-created').textContent = data.created;
                document.getElementById('issue-description').textContent = data.description;
                
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
                document.getElementById('issue-content').innerHTML = '<p>Error loading issue. Please try again.</p>';
            });
    }
    
    // Function to add a message to the chat
    function addMessage(text, sender) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}-message`;
        messageElement.textContent = text;
        chatMessages.appendChild(messageElement);
        
        // Scroll to the bottom of the chat
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to send message to backend
    function sendMessage(message, issueId) {
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                issue_id: issueId
            }),
        })
        .then(response => response.json())
        .then(data => {
            // Add AI response to chat
            addMessage(data.response, 'ai');
        })
        .catch(error => {
            console.error('Error sending message:', error);
            addMessage('Sorry, there was an error processing your request.', 'ai');
        });
    }
});