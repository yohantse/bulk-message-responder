import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Setup static files directory
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
app.use(express.static(path.join(__dirname, 'public')));

// JSON File Database setup
const DB_FILE = path.join(__dirname, 'queue_db.json');
let dbData = {
  messages: [],
  settings: {
    rpm_limit: '20',
    api_provider: 'mock',
    gemini_key: '',
    groq_key: ''
  }
};

async function initDb() {
  try {
    if (fs.existsSync(DB_FILE)) {
      const data = await fs.promises.readFile(DB_FILE, 'utf8');
      dbData = JSON.parse(data);
      
      // Ensure basic structure exists
      if (!dbData.messages) dbData.messages = [];
      if (!dbData.settings) dbData.settings = {};
      if (dbData.settings.rpm_limit === undefined) dbData.settings.rpm_limit = '20';
      if (dbData.settings.api_provider === undefined) dbData.settings.api_provider = 'mock';
      if (dbData.settings.gemini_key === undefined) dbData.settings.gemini_key = '';
      if (dbData.settings.groq_key === undefined) dbData.settings.groq_key = '';
    } else {
      await saveDb();
    }
  } catch (err) {
    console.error('Failed to initialize database, resetting to defaults:', err);
    await saveDb();
  }
}

async function saveDb() {
  await fs.promises.writeFile(DB_FILE, JSON.stringify(dbData, null, 2), 'utf8');
}

// Global SSE clients list
let clients = [];

function broadcast(event, data) {
  clients.forEach(client => {
    client.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  });
}

// Generate stats object helper
function getStats() {
  const total = dbData.messages.length;
  const queued = dbData.messages.filter(m => m.status === 'queued').length;
  const processing = dbData.messages.filter(m => m.status === 'processing').length;
  const completed = dbData.messages.filter(m => m.status === 'completed').length;
  const failed = dbData.messages.filter(m => m.status === 'failed').length;
  
  // Calculate RPM in the last 60 seconds
  const oneMinuteAgo = new Date(Date.now() - 60000).toISOString();
  const current_rpm = dbData.messages.filter(m => 
    m.status === 'completed' && 
    m.processed_at && 
    m.processed_at >= oneMinuteAgo
  ).length;

  return {
    total,
    queued,
    processing,
    completed,
    failed,
    current_rpm
  };
}

// SSE Connection Endpoint
app.get('/api/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  clients.push(res);

  // Send initial state
  res.write(`event: stats\ndata: ${JSON.stringify(getStats())}\n\n`);

  req.on('close', () => {
    clients = clients.filter(client => client !== res);
  });
});

// Settings Endpoints
app.get('/api/settings', (req, res) => {
  res.json(dbData.settings);
});

app.post('/api/settings', async (req, res) => {
  const { rpm_limit, api_provider, gemini_key, groq_key } = req.body;
  try {
    if (rpm_limit !== undefined) dbData.settings.rpm_limit = rpm_limit.toString();
    if (api_provider !== undefined) dbData.settings.api_provider = api_provider;
    if (gemini_key !== undefined) dbData.settings.gemini_key = gemini_key;
    if (groq_key !== undefined) dbData.settings.groq_key = groq_key;
    
    await saveDb();

    // Trigger the worker to apply speed changes or process messages
    triggerWorker();

    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Webhook endpoint (Ingests message to queue immediately and disconnects)
app.post('/api/webhook', async (req, res) => {
  const { phone, message } = req.body;
  if (!phone || !message) {
    return res.status(400).json({ error: 'Missing phone or message body' });
  }

  const msgId = 'msg_' + Math.random().toString(36).substr(2, 9);
  const createdAt = new Date().toISOString();

  try {
    const newMsg = {
      id: msgId,
      phone,
      message,
      status: 'queued',
      intent: null,
      urgency: null,
      language: null,
      extracted_entities: null,
      draft_response: null,
      error: null,
      created_at: createdAt,
      processed_at: null
    };

    dbData.messages.push(newMsg);
    await saveDb();

    // Broadcast stats and the new message immediately
    broadcast('stats', getStats());
    broadcast('message_queued', newMsg);

    // Respond within milliseconds to avoid webhook timeouts
    res.status(200).json({ status: 'queued', messageId: msgId });

    // Trigger the background processing worker asynchronously
    triggerWorker();
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Bulk Simulator Endpoint
app.post('/api/simulate-bulk', async (req, res) => {
  const { count, type } = req.body;
  if (!count) return res.status(400).json({ error: 'Missing count parameter' });

  const templates = [
    { phone: '+12025550143', message: 'Hi there, is my package order #99482 arriving today?' },
    { phone: '+13125550187', message: 'I need to cancel my appointment scheduled for tomorrow.' },
    { phone: '+14155550192', message: 'The item I received is broken, can I get a refund?' },
    { phone: '+16175550122', message: 'What are your store hours on Saturday?' },
    { phone: '+17185550156', message: 'Speak to a human representative please, this is urgent!' },
    { phone: '+15125550119', message: 'Can I book a table for 4 people on July 10th?' },
    { phone: '+12065550174', message: 'Is there free shipping for order #77312?' }
  ];

  try {
    const createdAt = new Date().toISOString();
    for (let i = 0; i < count; i++) {
      let t;
      if (type === 'mixed') {
        t = templates[i % templates.length];
      } else {
        t = templates[Math.floor(Math.random() * templates.length)];
      }

      // Add phone variety
      const phone = t.phone.slice(0, -3) + String(Math.floor(100 + Math.random() * 900));
      const msgId = 'msg_' + Math.random().toString(36).substr(2, 9) + '_' + i;
      
      dbData.messages.push({
        id: msgId,
        phone,
        message: t.message,
        status: 'queued',
        intent: null,
        urgency: null,
        language: null,
        extracted_entities: null,
        draft_response: null,
        error: null,
        created_at: createdAt,
        processed_at: null
      });
    }

    await saveDb();

    broadcast('stats', getStats());
    broadcast('bulk_queued', { count });

    res.json({ success: true, count });
    
    // Trigger background worker
    triggerWorker();
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get Messages
app.get('/api/messages', (req, res) => {
  const limit = parseInt(req.query.limit) || 100;
  // Sort messages descending by created_at
  const sorted = [...dbData.messages]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, limit);
  res.json(sorted);
});

// Clear Database Endpoint
app.post('/api/clear', async (req, res) => {
  try {
    dbData.messages = [];
    await saveDb();
    broadcast('stats', getStats());
    broadcast('cleared', {});
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// --- WORKER PIPELINE ---

let workerRunning = false;

function triggerWorker() {
  if (workerRunning) return;
  runWorker().catch(err => {
    console.error('Worker run failed:', err);
    workerRunning = false;
  });
}

async function runWorker() {
  workerRunning = true;

  while (true) {
    // 1. Get next queued message (oldest is first in queue)
    const msg = dbData.messages.find(m => m.status === 'queued');
    if (!msg) {
      break;
    }

    // 2. Set status to processing
    msg.status = 'processing';
    await saveDb();
    broadcast('message_updated', { id: msg.id, status: 'processing' });
    broadcast('stats', getStats());

    // 3. Get configurations
    const provider = dbData.settings.api_provider || 'mock';
    const rpmLimit = parseInt(dbData.settings.rpm_limit) || 20;

    let result;
    const startTime = Date.now();
    try {
      result = await callAI(provider, msg.message, dbData.settings);
      
      // Update entry details
      msg.status = 'completed';
      msg.intent = result.customer_intent;
      msg.urgency = result.urgency_score;
      msg.language = result.detected_language;
      msg.extracted_entities = result.extracted_entities;
      msg.draft_response = result.draft_response;
      msg.processed_at = new Date().toISOString();
      await saveDb();

      broadcast('message_updated', {
        id: msg.id,
        status: 'completed',
        intent: msg.intent,
        urgency: msg.urgency,
        language: msg.language,
        extracted_entities: msg.extracted_entities,
        draft_response: msg.draft_response
      });

    } catch (err) {
      console.error(`Error processing message ${msg.id}:`, err.message);
      msg.status = 'failed';
      msg.error = err.message;
      msg.processed_at = new Date().toISOString();
      await saveDb();
      broadcast('message_updated', { id: msg.id, status: 'failed', error: err.message });
    }

    broadcast('stats', getStats());

    // 4. Rate limiting delay calculation
    const intervalMs = Math.ceil(60000 / rpmLimit);
    const elapsedMs = Date.now() - startTime;
    const remainingDelay = Math.max(0, intervalMs - elapsedMs);

    if (remainingDelay > 0) {
      broadcast('worker_throttled', { remainingDelay });
      await sleep(remainingDelay);
    }
  }

  workerRunning = false;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Call AI logic matching Groq, Gemini or Fallback Mock
async function callAI(provider, messageText, settings) {
  const schemaDescription = `
{
  "customer_intent": "order_inquiry | booking_request | complaint | general_faq | human_escalation",
  "urgency_score": "low | medium | high",
  "detected_language": "string (ISO 639-1 code)",
  "extracted_entities": {
    "order_id": "string or null",
    "requested_date": "string or null"
  },
  "draft_response": "The suggested text reply to the customer goes here"
}
`;

  if (provider === 'gemini') {
    const apiKey = settings.gemini_key;
    if (!apiKey) throw new Error('Gemini API key is not configured');

    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
    const prompt = `Analyze the customer message and extract the following structured details. Output strictly JSON.
Schema:
${schemaDescription}

Customer Message: "${messageText}"`;

    const payload = {
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        responseMimeType: 'application/json'
      }
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Gemini API error: ${response.status} - ${errText}`);
    }

    const data = await response.json();
    const rawText = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!rawText) throw new Error('Empty response from Gemini');
    return JSON.parse(rawText.trim());
  }

  if (provider === 'groq') {
    const apiKey = settings.groq_key;
    if (!apiKey) throw new Error('Groq API key is not configured');

    const url = 'https://api.groq.com/openai/v1/chat/completions';
    const payload = {
      model: 'llama-3.1-8b-instant',
      messages: [
        {
          role: 'system',
          content: 'You are an advanced message parser. You must parse the customer message and return a valid JSON object matching the requested schema. Return absolutely nothing else.'
        },
        {
          role: 'user',
          content: `Schema:\n${schemaDescription}\n\nCustomer Message: "${messageText}"`
        }
      ],
      response_format: {
        type: 'json_object'
      }
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Groq API error: ${response.status} - ${errText}`);
    }

    const data = await response.json();
    const rawText = data.choices?.[0]?.message?.content;
    if (!rawText) throw new Error('Empty response from Groq');
    return JSON.parse(rawText.trim());
  }

  // Fallback Mock API simulation
  await sleep(500 + Math.random() * 700);

  let intent = 'general_faq';
  let urgency = 'low';
  let language = 'en';
  let orderId = null;
  let date = null;
  let responseText = '';

  const lowerText = messageText.toLowerCase();

  if (lowerText.includes('cancel') || lowerText.includes('broken') || lowerText.includes('refund')) {
    intent = 'complaint';
    urgency = 'high';
    responseText = 'I apologize for the issue with your item. I have forwarded your message to a supervisor, who will process your refund or replacement immediately.';
  } else if (lowerText.includes('book') || lowerText.includes('appointment') || lowerText.includes('reserve') || lowerText.includes('table')) {
    intent = 'booking_request';
    urgency = 'medium';
    const matches = lowerText.match(/(?:on\s+)?([a-z]+\s+\d{1,2}(?:th|st|nd|rd)?)/i);
    date = matches ? matches[1] : 'requested date';
    responseText = `Thanks for your booking request! I've noted down your interest for ${date} and our scheduling team will call you to finalize.`;
  } else if (lowerText.includes('order') || lowerText.includes('#') || lowerText.includes('shipping')) {
    intent = 'order_inquiry';
    urgency = 'low';
    const orderMatch = messageText.match(/#\d+/);
    orderId = orderMatch ? orderMatch[0] : 'order #1092';
    responseText = `I'd be glad to look up order ${orderId} for you. Let me check the shipment tracking and get back to you in a few minutes.`;
  } else if (lowerText.includes('human') || lowerText.includes('representative') || lowerText.includes('speak') || lowerText.includes('urgent')) {
    intent = 'human_escalation';
    urgency = 'high';
    responseText = 'Your request has been escalated. A human customer agent will join this conversation shortly.';
  } else {
    responseText = 'Thank you for reaching out! A representative will respond to your message as soon as possible.';
  }

  return {
    customer_intent: intent,
    urgency_score: urgency,
    detected_language: language,
    extracted_entities: {
      order_id: orderId,
      requested_date: date
    },
    draft_response: responseText
  };
}

// Start Server
initDb().then(() => {
  app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
    triggerWorker();
  });
});
