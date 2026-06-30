document.addEventListener("DOMContentLoaded", function () {
    function updateNotificationCount() {
        fetch("/get_notification_count", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        })
            .then((response) => response.json())
            .then((data) => {
                const countElement = document.querySelector(".notification_number");
                if (!countElement || !Array.isArray(data) || !data.length) {
                    return;
                }
                if (data[0].count > 0) {
                    countElement.textContent = data[0].count;
                    countElement.style.display = "block";
                } else {
                    countElement.style.display = "none";
                }
            })
            .catch((error) => console.error("Error fetching notification count:", error));
    }

    function markAllNotificationsSeen() {
        return fetch("/view_all_notifications", {
            method: "GET",
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.status === "success") {
                    updateNotificationCount();
                    const notificationDropdown = document.querySelector("#notification_dd");
                    if (notificationDropdown) {
                        notificationDropdown.innerHTML = "";
                    }
                } else {
                    console.error("Error marking all notifications as seen:", data.message);
                }
            })
            .catch((error) => console.error("Error marking all notifications as seen:", error));
    }

    function markNotificationSeen(notificationId) {
        if (!notificationId) {
            console.error("Notification ID is missing");
            return;
        }

        fetch("/mark_notification_seen", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({notification_id: notificationId}),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.status === "success") {
                    updateNotificationCount();
                    const notificationItem = document.querySelector(
                        `.notification_item[data-id="${notificationId}"]`
                    );
                    if (notificationItem) {
                        notificationItem.remove();
                    }
                } else {
                    console.error("Error marking notification as seen:", data.message);
                }
            })
            .catch((error) => console.error("Error marking notification as seen:", error));
    }

    function fetchNotifications() {
        fetch("/get_notifications", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        })
            .then((response) => response.json())
            .then((notifications) => {
                const notificationDropdown = document.querySelector("#notification_dd");
                if (!notificationDropdown) {
                    return;
                }
                const notificationList = notificationDropdown.querySelector(".notification_ul");
                if (!notificationList) {
                    return;
                }

                notificationList.innerHTML = "";

                notifications.forEach((notification) => {
                    // Create a new notification item
                    const notificationItem = document.createElement("li");
                    notificationItem.className = "notification_item";
                    notificationItem.setAttribute("data-id", notification.id);

                    // Add content to the item
                    const itemContent = document.createElement("a");
                    itemContent.href = notification.url;
                    itemContent.className = "mx-auto link";
                    itemContent.textContent = notification.message;

                    notificationItem.appendChild(itemContent);
                    notificationList.appendChild(notificationItem);

                    // Add click listener to mark notification as seen
                    notificationItem.addEventListener("click", function () {
                        const notificationId = this.getAttribute("data-id");
                        markNotificationSeen(notificationId);
                    });
                });

                // Add the "View All Notifications" link
                const viewAllLink = document.createElement("li");
                viewAllLink.className = "show_all";
                viewAllLink.innerHTML =
                    '<a href="#" class="link" onclick="viewAllNotifications()" id="view_all_notif">View All Notifications</a>';
                notificationList.appendChild(viewAllLink);
            })
            .catch((error) => console.error("Error fetching notifications:", error));
    }

    window.viewAllNotifications = function () {
        // Event.preventDefault(); // Prevent the default action of the link

        markAllNotificationsSeen().then(() => {
            // Redirect after notifications are marked as seen
            window.location.href = "/serviceprovider/update/suggests";
        });
    };

    var toggleButton = document.getElementById("show_notification");
    const field = document.getElementById("notification_dd");

    if (toggleButton) {
        toggleButton.addEventListener("click", function () {
            if (!field) {
                return;
            }
            if (field.style.display === "none" || field.style.display === "") {
                field.style.display = "block";
                fetchNotifications();
            } else {
                field.style.display = "none";
            }
        });
    }

    document.addEventListener("click", function (event) {
        if (!toggleButton || !field) {
            return;
        }
        if (!toggleButton.contains(event.target) && !field.contains(event.target)) {
            field.style.display = "none";
        }
    });

    updateNotificationCount();
});
