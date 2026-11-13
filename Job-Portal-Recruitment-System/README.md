# Job Portal & Recruitment Management System

## 1. Project Overview

The Job Portal & Recruitment Management System is a web-based application developed using Python Flask and SQLite. It provides a platform for managing candidates, companies, job opportunities and job applications.

The system simplifies recruitment activities by providing candidate registration, company management, job posting, application tracking and administrative operations through a web interface.

## 2. Objectives

- Develop a web-based recruitment management platform.
- Manage candidate and company information.
- Enable job posting and job searching.
- Allow candidates to apply for available jobs.
- Manage and track job applications.
- Provide administrative control over recruitment activities.

## 3. Technologies Used

- **Python:** Backend programming language.
- **Flask:** Web application framework.
- **SQLite:** Database management.
- **HTML:** Webpage structure.
- **CSS:** User interface styling.
- **Jinja2:** Dynamic webpage rendering.

## 4. Main Features

### Admin Management
- Admin login and authentication.
- Admin dashboard with application statistics.
- Candidate management.
- Company management.
- Job management.
- Application management.
- Application status updates.

### Candidate Management
- Candidate registration.
- Candidate information management.
- Skills and education details.
- Experience information.

### Company Management
- Company registration.
- Company information management.
- Company listing.

### Job Management
- Job posting.
- Job listing.
- Job searching.
- Job management.

### Application Management
- Candidate job applications.
- Resume upload.
- Application tracking.
- Application status management.

## 5. System Architecture

The application follows a basic three-layer architecture:

1. **Frontend Layer:** HTML and CSS provide the user interface.
2. **Backend Layer:** Python Flask handles application logic and HTTP requests.
3. **Database Layer:** SQLite stores candidate, company, job and application information.

## 6. Project Structure

```text
Job-Portal-Recruitment-System/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── data.db
├── uploads/
└── .venv/
```

Note: The database, uploaded resumes and virtual environment are excluded from the public GitHub repository.

## 7. Installation and Setup

### Prerequisites
- Python 3 installed.
- Visual Studio Code.
- Git.
- Web browser.

### Step 1: Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### Step 2: Navigate to the Project

```bash
cd Job-Portal-Recruitment-System
```

### Step 3: Create a Virtual Environment

```bash
python -m venv .venv
```

### Step 4: Activate Virtual Environment

For Windows:

```bash
.venv\Scripts\activate
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6: Run the Application

```bash
python app.py
```

### Step 7: Open in Browser

```text
http://127.0.0.1:5001
```

## 8. Database

SQLite is used as the database for storing application information, including candidate details, company information, job listings and applications.

The database is initialized by the application as configured in the source code.

## 9. Future Enhancements

- Advanced candidate and recruiter authentication.
- Improved search and filtering functionality.
- Email notifications.
- Enhanced dashboard analytics.
- Cloud-based deployment.
- Improved user interface and responsive design.

## 10. Conclusion

The Job Portal & Recruitment Management System provides a web-based solution for organizing recruitment activities. It demonstrates the implementation of Python Flask, database integration, web development and administrative management functionalities.