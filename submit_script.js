(function() {
    const nameInput = document.querySelector('input[name="Name"]');
    const uidInput = document.querySelector('input[name="FreeFireUID"]');
    const submitBtn = document.querySelector('input[type="submit"]');

    if (nameInput && uidInput && submitBtn) {
        nameInput.value = "HUKEX";
        uidInput.value = "877998709";
        
        // Trigger input events to ensure the site's logic detects the change
        nameInput.dispatchEvent(new Event('input', { bubbles: true }));
        uidInput.dispatchEvent(new Event('input', { bubbles: true }));

        console.log("Form filled. Submitting...");
        submitBtn.click();
        return "Success: Form submitted.";
    } else {
        const errorMsg = "Error: Form fields not found.";
        console.error(errorMsg);
        return errorMsg;
    }
})();
