import { initializeApp } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-app.js";
import { getFirestore, collection, getDocs, query, orderBy, getCountFromServer } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyC2QQCuI8-21Ah-mSqO-RStY-yZvmMc1Qo",
  authDomain: "agency-database-c8d6c.firebaseapp.com",
  projectId: "agency-database-c8d6c",
  storageBucket: "agency-database-c8d6c.firebasestorage.app",
  messagingSenderId: "46488370768",
  appId: "1:46488370768:web:852e854a0a1514c4741b55"
}

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// Fetch total model count
async function fetchModelCount() {
  const coll = collection(db, "models");
  const snapshot = await getCountFromServer(coll);
  const totalModels = snapshot.data().count;

  const searchInput = document.getElementById("model-count");
  const modelCount = document.getElementById("model-count");
  if (modelCount) {
    modelCount.textContent = `Total models in database: ${totalModels}`;
  }
}
fetchModelCount()



async function displayScrapeLog() {
  const logRef = collection(db, "scrape_logs");
  const q = query(logRef, orderBy("timestamp", "desc"));
  const snapshot = await getDocs(q);

  const tbody = document.querySelector("#scrape-log tbody");
  tbody.innerHTML = ""; // clear previous

  snapshot.forEach(doc => {
    const data = doc.data();
    const row = document.createElement("tr");

    const date = new Date(data.timestamp.seconds * 1000).toLocaleString();

    const successCell = document.createElement("td");
    successCell.textContent = data.success ? "✅" : "❌";

    if (data.success === false && data.error) {
      successCell.classList.add("has-tooltip");
      successCell.title = data.error;
    }

    row.innerHTML = `
      <td>${date}</td>
      <td></td> <!-- Placeholder for success -->
      <td>${data.board || "—"}</td>
      <td>${data.added ?? 0}</td>
      <td>${data.removed ?? 0}</td>
    `;

    // Insert success cell manually (to include tooltip logic)
    row.children[1].replaceWith(successCell);

    tbody.appendChild(row);
  });
}


displayScrapeLog();
