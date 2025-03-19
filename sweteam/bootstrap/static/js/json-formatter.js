/**
 * JSON Formatter Utility
 * 
 * This utility provides functions to format JSON data into a collapsible HTML structure
 * for better visualization of nested JSON objects.
 */

// Function to format JSON data into a collapsible HTML structure
function formatJSON(data, isCollapsible = true) {
    const container = document.createElement('div');
    container.className = 'json-item';
    
    if (data === null) {
        const nullSpan = document.createElement('span');
        nullSpan.className = 'json-null';
        nullSpan.textContent = 'null';
        container.appendChild(nullSpan);
        return container;
    }
    
    if (typeof data === 'boolean') {
        const boolSpan = document.createElement('span');
        boolSpan.className = 'json-boolean';
        boolSpan.textContent = data.toString();
        container.appendChild(boolSpan);
        return container;
    }
    
    if (typeof data === 'number') {
        const numSpan = document.createElement('span');
        numSpan.className = 'json-number';
        numSpan.textContent = data.toString();
        container.appendChild(numSpan);
        return container;
    }
    
    if (typeof data === 'string') {
        const strSpan = document.createElement('span');
        strSpan.className = 'json-string';
        strSpan.textContent = `"${data}"`;
        container.appendChild(strSpan);
        return container;
    }
    
    if (Array.isArray(data)) {
        if (data.length === 0) {
            container.textContent = '[]';
            return container;
        }
        
        const isCollapsibleArray = isCollapsible && data.length > 0;
        
        if (isCollapsibleArray) {
            // Create a wrapper for the collapsible header
            const headerWrapper = document.createElement('span');
            headerWrapper.className = 'collapsible';
            headerWrapper.textContent = '[';
            container.appendChild(headerWrapper);
            
            // Create content container
            const contentDiv = document.createElement('div');
            contentDiv.className = 'json-content';
            
            // Add items
            data.forEach((item, index) => {
                const itemWrapper = document.createElement('div');
                itemWrapper.className = 'json-array-item';
                
                // Add the formatted item
                itemWrapper.appendChild(formatJSON(item, true));
                
                // Add comma if not the last item
                if (index < data.length - 1) {
                    const comma = document.createElement('span');
                    comma.className = 'json-comma';
                    comma.textContent = ',';
                    itemWrapper.appendChild(comma);
                }
                
                contentDiv.appendChild(itemWrapper);
            });
            
            container.appendChild(contentDiv);
            
            // Add closing bracket
            const closingBracket = document.createElement('span');
            closingBracket.className = 'json-closing';
            closingBracket.textContent = ']';
            container.appendChild(closingBracket);
        } else {
            // Simple non-collapsible array
            let arrayText = '[';
            
            data.forEach((item, index) => {
                const itemContainer = formatJSON(item, false);
                container.appendChild(document.createTextNode(index === 0 ? '[' : ''));
                container.appendChild(itemContainer);
                
                if (index < data.length - 1) {
                    container.appendChild(document.createTextNode(', '));
                } else {
                    container.appendChild(document.createTextNode(']'));
                }
            });
            
            if (data.length === 0) {
                container.textContent = '[]';
            }
        }
        
        return container;
    }
    
    // Object handling
    if (typeof data === 'object') {
        const keys = Object.keys(data);
        
        if (keys.length === 0) {
            container.textContent = '{}';
            return container;
        }
        
        const isCollapsibleObj = isCollapsible && keys.length > 0;
        
        if (isCollapsibleObj) {
            // Create a wrapper for the collapsible header
            const headerWrapper = document.createElement('span');
            headerWrapper.className = 'collapsible';
            headerWrapper.textContent = '{';
            container.appendChild(headerWrapper);
            
            // Create content container
            const contentDiv = document.createElement('div');
            contentDiv.className = 'json-content';
            
            // Add properties
            keys.forEach((key, index) => {
                const propertyWrapper = document.createElement('div');
                propertyWrapper.className = 'json-property';
                
                // Create key element
                const keyElement = document.createElement('span');
                keyElement.className = 'json-key';
                keyElement.textContent = `"${key}": `;
                propertyWrapper.appendChild(keyElement);
                
                // Add the value
                propertyWrapper.appendChild(formatJSON(data[key], true));
                
                // Add comma if not the last property
                if (index < keys.length - 1) {
                    const comma = document.createElement('span');
                    comma.className = 'json-comma';
                    comma.textContent = ',';
                    propertyWrapper.appendChild(comma);
                }
                
                contentDiv.appendChild(propertyWrapper);
            });
            
            container.appendChild(contentDiv);
            
            // Add closing brace
            const closingBrace = document.createElement('div');
            closingBrace.className = 'json-closing';
            closingBrace.textContent = '}';
            container.appendChild(closingBrace);
        } else {
            // Simple non-collapsible object
            container.appendChild(document.createTextNode('{'));
            
            keys.forEach((key, index) => {
                const keyElement = document.createElement('span');
                keyElement.className = 'json-key';
                keyElement.textContent = `"${key}": `;
                container.appendChild(keyElement);
                
                container.appendChild(formatJSON(data[key], false));
                
                if (index < keys.length - 1) {
                    container.appendChild(document.createTextNode(', '));
                }
            });
            
            container.appendChild(document.createTextNode('}'));
        }
        
        return container;
    }
    
    // Fallback for any other type
    container.textContent = String(data);
    return container;
}

// Function to add event listeners to collapsible elements
function addCollapsibleListeners() {
    document.querySelectorAll('.collapsible').forEach(element => {
        // Add collapsed class by default to start with collapsed view
        element.classList.add('collapsed');
        
        // Hide content by default
        const content = element.nextElementSibling;
        if (content && content.classList.contains('json-content')) {
            content.classList.add('hidden');
        }
        
        // Add click event listener
        element.addEventListener('click', function(e) {
            e.stopPropagation();
            this.classList.toggle('collapsed');
            
            // Toggle visibility of the next sibling (content div)
            const content = this.nextElementSibling;
            if (content && content.classList.contains('json-content')) {
                content.classList.toggle('hidden');
                // If shift is held, update all child collapsible nodes
                if (e.shiftKey) {
                    // Determine the new state; if current is collapsed then we want to collapse children, otherwise expand them.
                    const shouldCollapse = this.classList.contains('collapsed');
                    setCollapseState(content, shouldCollapse);
                }
            }
        });
    });
}
// Function to recursively set collapse state for all collapsible subnodes under a container
function setCollapseState(container, collapse) {
    container.querySelectorAll('.collapsible').forEach(el => {
        if (collapse) {
            el.classList.add('collapsed');
            if (el.nextElementSibling && el.nextElementSibling.classList.contains('json-content')) {
                el.nextElementSibling.classList.add('hidden');
            }
        } else {
            el.classList.remove('collapsed');
            if (el.nextElementSibling && el.nextElementSibling.classList.contains('json-content')) {
                el.nextElementSibling.classList.remove('hidden');
            }
        }
    });
}


// Function to parse and format JSON string
function parseAndFormatJSON(jsonString, container) {
    try {
        // Try to parse the string as JSON
        const jsonData = JSON.parse(jsonString);
        
        // Clear the container
        container.innerHTML = '';
        
        // Create JSON formatter
        const jsonFormatter = document.createElement('div');
        jsonFormatter.className = 'json-formatter';
        
        // Format and append the JSON
        jsonFormatter.appendChild(formatJSON(jsonData));
        container.appendChild(jsonFormatter);
        
        // Add event listeners for collapsible sections
        addCollapsibleListeners();
        
        return true;
    } catch (e) {
        console.error('Error parsing JSON:', e);
        return false;
    }
}