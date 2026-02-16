# SafeEats — Specification Document

## User Stories

### User Story 1: Stronger Ingredient Parsing & Allergen Inference

- **1.1 – Rich allergen mapping**
  - As a restaurant owner, I want the system to recognize common ingredients and automatically infer associated allergens and dietary restrictions so that my menu items are accurately labeled without requiring manual tagging.

- **1.2 – Ingredient variant handling**
  - As a restaurant manager, I want the system to understand common ingredient variants and abbreviations (e.g., "parm," "parmigiano reggiano") so that allergen detection remains accurate even when ingredient names differ.

- **1.3 – Dietary rule inference**
  - As a restaurant owner, I want ingredients like bacon or crab to automatically apply dietary and allergen rules (e.g., non-vegetarian, shellfish), so users with dietary restrictions receive correct recommendations.

- **1.4 – Cached ingredient parsing**
  - As a restaurant staff member, I want ingredient parsing results to be cached, so repeated ingredient entries do not slow down the system or trigger unnecessary AI calls.

### User Story 2: Bulk Editing & Menu Management

- **2.1 – Bulk menu updates**
  - As a restaurant manager, I want to edit tags, allergens, or dietary labels for multiple menu items at once so I can efficiently manage large or frequently changing menus.

- **2.2 – Duplicate and archive items**
  - As a restaurant manager, I want to edit tags, allergens, or dietary labels for multiple menu items at once so I can efficiently manage large or frequently changing menus.

- **2.3 – CSV import/export**
  - As a restaurant manager, I want to import and export menu items using CSV files so I can edit menus offline and integrate SafeEats with my existing workflows.

### User Story 3: Restaurant Profile Management

- **3.1 – Edit restaurant profile**
  - As a restaurant owner, I want to edit my restaurant's contact information, address, and description so customers receive accurate and helpful details when viewing my restaurant.

- **3.2 – Allergen and dietary policy notes**
  - As a restaurant owner, I want to add notes explaining my allergen handling and dietary policies so users can make informed decisions about ordering from my restaurant.

- **3.3 – Upload branding images**
  - As a restaurant manager, I want to upload a logo or hero image for my restaurant profile, so my restaurant is visually recognizable and professional within the app.

### User Story 4: Multi-User Access & Role Management

- **4.1 – Multiple accounts per restaurant**
  - As a restaurant owner, I want multiple users to manage the same restaurant account so responsibilities can be shared among staff.

- **4.2 – Role-based permissions**
  - As a restaurant owner, I want to assign roles (Owner/Manager or Staff) to users so each person only has access to the features they need.

- **4.3 – Restricted access by role**
  - As a staff member, I want to edit menu items but not access billing or administrative settings, so I can safely perform my duties without risking sensitive information.

---

## Requirements

### Functional Requirements

#### Definite

**Enhanced Ingredient Parsing and Allergen Inference**
We plan to replace the current exact-match parsing with a more robust approach. A structured mapping table will link common ingredients to their associated allergen categories (aligned with the nine FDA major allergens) and dietary flags (vegetarian, vegan, gluten-free, halal, kosher). This table will also handle common abbreviations and regional variants by mapping them to canonical ingredient names (e.g., "parm" and "parmigiano reggiano" both resolve to "parmesan" → dairy). When ingredients are parsed, the system will automatically infer dietary restrictions, flagging items as non-vegetarian for meat products, non-vegan for animal-derived products, and not gluten-free for wheat-containing ingredients. All inferred tags will be presented to the user for review before saving.

**Graceful AI Degradation**
If the AI parsing service is unavailable, returns an error, or is disabled in configuration, the system will display a notification and fall back to manual tagging. All allergen and dietary tag selection must function independently of the AI service at all times.

**Menu Item Image Upload**
An image upload field will be added to the menu item form. Users will be able to upload a single image per item, which will be stored in Supabase Storage. Uploaded images will appear as thumbnails on the menu list and at full size in the edit view, while items without an image will show a default placeholder.

**Restaurant Profile Management**
A dedicated settings page shall allow authenticated users to view and update their restaurant's name, phone number, email, address, and description. This page will also include a free-text field for allergen handling and dietary policy notes, along with the ability to upload a logo and hero/banner image. All input will be validated on both the frontend and backend.

#### Perhaps

**Cached Ingredient Parsing**
AI parsing results will be cached in the database, keyed by a normalized version of the ingredient string. When a submission matches a cached entry, the stored results will be returned without making a new API call.

**Bulk Tag Editing**
A bulk editing interface will allow users to select multiple menu items via checkboxes and apply or remove allergen tags and dietary labels across all selected items in a single action. Before committing, a confirmation summary will display the proposed changes and the number of affected items.

**Menu Item Duplication and Archiving**
Users will be able to duplicate a menu item, creating a new editable copy pre-populated with the original's data. Archiving will also be supported, removing items from the active menu view without deleting the underlying database record. An "Archived" filter will allow users to browse and restore previously archived items.

**CSV Export**
Users will be able to export their active menu items to a downloadable CSV file containing columns for name, description, price, ingredients, allergen tags, and dietary labels.

#### Improbable

**Multi-User Access and Role-Based Permissions**
Restaurant Owners will be able to invite users by email, assign roles (Owner/Manager or Staff), and manage a team list. Staff users will be restricted to menu item operations only. Navigation and feature visibility will adapt based on the authenticated user's role.

**CSV Import**
Users will be able to upload a CSV file of menu items through an import flow that includes column mapping, a row-level validation preview, and the ability to skip or correct invalid entries before confirming the import.

---

### Non-Functional Requirements

**Usability**
- The interface must be intuitive enough that a restaurant staff member with no technical training can add a menu item and review allergen tags within 5 minutes of first use.
- The UI must be mobile-friendly for use on phones or tablets.
- The app must return descriptive error messages.

**Reliability**
- The system must handle AI API failures gracefully, falling back to manual tagging without data loss.
- Cached ingredient results must return consistently.

**Performance**
- Menu item list views should load within 3 seconds for restaurants with up to 200 items.
- Cached ingredient parsing lookups should return in under 500 ms.
- CSV imports/exports of menus containing up to 500 items should complete in under 10 seconds.

**Supportability**
- The codebase should follow consistent naming conventions and include README documentation sufficient for a future development team to set up and run the project locally.
- The application should be deployable to Render (current host) with no manual server configuration beyond environment variables.
- Switching AI providers should require only configuration changes and no major code refactoring.
- API/parsing failures should be logged.

**Constraints**
- The system must operate within the free tiers of all external services (Supabase, Google Gemini API, Render hosting).
- The system must not store any personally identifiable customer data.

**Interface Requirements**
- The frontend is a single-page React application communicating with the FastAPI backend via RESTful JSON APIs.
- Authentication is handled through Supabase Auth; the backend validates Supabase JWTs on every protected endpoint.
- The UI design follows the Figma mockups agreed upon with the client (see linked Figma file).
- The system is designed as a web application; mobile responsiveness is desirable, but a native mobile app is out of scope for this semester.

---

### Interfaces

**User Interface (GUI)**
A React-based single-page web application providing forms and views for menu item management, ingredient parsing, restaurant profile editing, and allergen/tag management. The design follows the Figma mockups provided by the previous development team and agreed upon with the client.

Figma Prototype: https://www.figma.com/design/garj1ogVXkEgFSJLZ7AHXo/SafeEats-S25?node-id=0-1&p=f

**Backend API**
A RESTful API built with FastAPI, exposing endpoints for menu item CRUD, AI-powered ingredient parsing, restaurant profile management, image uploads, and CSV export. All endpoints are scoped by restaurant ID and require a valid Supabase JWT. Responses use JSON format, and errors return standardized status codes with descriptive messages.

**External Services**
- **Supabase** — PostgreSQL database for all application data, Supabase Auth for user authentication and session management, and Supabase Storage for menu item and restaurant profile images.
- **Google Gemini API** — Used for AI-powered ingredient parsing and allergen inference. Accessed via the free tier; the backend is configured to degrade gracefully if the service is unavailable.
- **Render** — Hosts both the React frontend and FastAPI backend. Deployment is configured via environment variables with no manual server setup required.
