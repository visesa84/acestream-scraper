let usersModal = null;

document.addEventListener('DOMContentLoaded', function() {
    const modalEl = document.getElementById('usersManagementModal');
    if (modalEl) {
        usersModal = new bootstrap.Modal(modalEl);
    }

    const addUserForm = document.getElementById('addUserForm');
    if (addUserForm) {
        addUserForm.addEventListener('submit', handleAddUser);
    }
});

function openUsersModal() {
    loadUsers();
    if (usersModal) {
        usersModal.show();
    }
}

async function loadUsers() {
    const tbody = document.getElementById('usersTableBody');
    try {
        const response = await fetch('/api/users/');
        if (!response.ok) throw new Error('Error fetching users');
        
        const users = await response.json();
        
        if (!users || users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3">No users found</td></tr>';
            return;
        }

        tbody.innerHTML = users.map(user => `
            <tr>
                <td>${user.id}</td>
                <td><strong>${user.username}</strong></td>
                <td>
                    <span class="badge ${user.is_admin ? 'bg-danger' : 'bg-secondary'}">
                        ${user.is_admin ? 'Administrator' : 'Standard User'}
                    </span>
                </td>
                <td>${user.created_at ? new Date(user.created_at).toLocaleString() : 'N/A'}</td>
                <td class="text-end">
                    <button class="btn btn-sm btn-outline-warning me-1" onclick="changePassword(${user.id}, '${user.username}')" title="Change Password">
                        <i class="bi bi-key"></i> Key
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteUser(${user.id}, '${user.username}')" title="Delete User">
                        <i class="bi bi-trash"></i> Delete
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading users:', error);
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-3">Failed to load users</td></tr>';
    }
}

async function handleAddUser(e) {
    e.preventDefault();
    const usernameInput = document.getElementById('newUsername');
    const passwordInput = document.getElementById('newPassword');
    const isAdminSelect = document.getElementById('newIsAdmin');

    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    const is_admin = isAdminSelect ? isAdminSelect.value === 'true' : false;

    if (!username || !password) return;

    try {
        const response = await fetch('/api/users/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, is_admin })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || 'Failed to create user');
            return;
        }

        usernameInput.value = '';
        passwordInput.value = '';
        if (isAdminSelect) isAdminSelect.value = 'false';
        loadUsers();
    } catch (error) {
        console.error('Error adding user:', error);
        alert('An error occurred while creating the user');
    }
}

async function changePassword(id, username) {
    const newPassword = prompt(`Enter new password for user "${username}":`);
    if (newPassword === null) return;
    
    if (!newPassword.trim()) {
        alert('Password cannot be empty.');
        return;
    }

    try {
        const response = await fetch(`/api/users/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: newPassword.trim() })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || 'Failed to update password');
            return;
        }

        alert(`Password for "${username}" updated successfully.`);
    } catch (error) {
        console.error('Error updating password:', error);
        alert('An error occurred while updating the password.');
    }
}

async function deleteUser(id, username) {
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) return;

    try {
        const response = await fetch(`/api/users/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            alert(data.error || 'Failed to delete user');
            return;
        }

        loadUsers();
    } catch (error) {
        console.error('Error deleting user:', error);
        alert('An error occurred while deleting the user');
    }
}