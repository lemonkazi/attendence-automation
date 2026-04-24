const API_BASE_URL = 'http://localhost:8502';

const elements = {
  time: document.getElementById('current-time'),
  date: document.getElementById('current-date'),
  recordingDate: document.getElementById('recording-date'),
  employeeSelect: document.getElementById('employee-select'),
  checkInBtn: document.getElementById('check-in-btn'),
  checkOutBtn: document.getElementById('check-out-btn'),
  toast: document.getElementById('toast')
};

const getCurrentTime = () => {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Dhaka',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  }).format(new Date());
};

const getRecordingTime = () => {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Dhaka',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  }).format(new Date());
};

const getTodayDate = () => {
  const now = new Date();
  const dhaka = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Dhaka',
    month: 'numeric',
    day: 'numeric',
    year: 'numeric'
  }).format(now);
  return dhaka.replace(/(\d+)\/(\d+)\/(\d+)/, '$1/$2/$3'); // Format as M/D/YYYY
};

const updateClock = () => {
  elements.time.textContent = getCurrentTime();
  elements.date.textContent = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Dhaka',
    dateStyle: 'full'
  }).format(new Date());
  
  // Update button highlights based on time
  const dhakaHour = parseInt(new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Dhaka',
    hour: '2-digit',
    hour12: false
  }).format(new Date()));
  
  const isAfterNoon = dhakaHour >= 12;
  
  if (isAfterNoon) {
    elements.checkInBtn.classList.remove('btn-primary');
    elements.checkInBtn.classList.add('btn-secondary');
    elements.checkOutBtn.classList.remove('btn-secondary');
    elements.checkOutBtn.classList.add('btn-primary');
  } else {
    elements.checkInBtn.classList.remove('btn-secondary');
    elements.checkInBtn.classList.add('btn-primary');
    elements.checkOutBtn.classList.remove('btn-primary');
    elements.checkOutBtn.classList.add('btn-secondary');
  }
};

const showToast = (message, type = 'success') => {
  elements.toast.textContent = message;
  elements.toast.className = `toast ${type}`;
  elements.toast.classList.remove('hidden');
  
  setTimeout(() => {
    elements.toast.classList.add('hidden');
  }, 3000);
};

const handleAttendance = async (action) => {
  const employee = elements.employeeSelect.value;
  if (!employee) {
    showToast('Please select an employee first', 'error');
    return;
  }

  const btn = action === 'checkin' ? elements.checkInBtn : elements.checkOutBtn;
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.textContent = 'Processing...';

  try {
    const response = await fetch(`${API_BASE_URL}/attendance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        employee: employee,
        action: action,
        date: getTodayDate(),
        time: getRecordingTime()
      })
    });

    if (response.ok) {
      const actionText = action === 'checkin' ? 'checked-in' : 'checked-out';
      showToast(`Success! ${employee} ${actionText}`, 'success');
    } else {
      throw new Error('Failed to update attendance');
    }
  } catch (error) {
    console.error(error);
    showToast('Failed to update attendance. Please try again.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
};

// Event Listeners
elements.checkInBtn.addEventListener('click', () => handleAttendance('checkin'));
elements.checkOutBtn.addEventListener('click', () => handleAttendance('checkout'));

// Save selected employee to storage
elements.employeeSelect.addEventListener('change', (e) => {
  chrome.storage.local.set({ selectedEmployee: e.target.value });
});

// Load saved employee
chrome.storage.local.get(['selectedEmployee'], (result) => {
  if (result.selectedEmployee) {
    elements.employeeSelect.value = result.selectedEmployee;
  }
});

// Initialization
elements.recordingDate.textContent = getTodayDate();
setInterval(updateClock, 1000);
updateClock();
