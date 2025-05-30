import { initializeApp } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-app.js";
import { getFirestore, collection, getDocs, query, orderBy } from "https://www.gstatic.com/firebasejs/10.11.0/firebase-firestore.js";

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

async function loadLogs() {
  const logList = document.getElementById("log-list");
  logList.innerHTML = "";

  const q = query(collection(db, "scrape_logs"), orderBy("timestamp", "desc"));
  const snapshot = await getDocs(q);

  snapshot.forEach(doc => {
    const data = doc.data();
    const item = document.createElement("li");
    item.textContent = `${new Date(data.timestamp.seconds * 1000).toLocaleString()}: ${data.added} added, ${data.removed} removed from ${data.board}`;
    logList.appendChild(item);
  });
}

loadLogs();
