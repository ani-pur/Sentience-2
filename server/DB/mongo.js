const { MongoClient } = require('mongodb')

const uri = process.env.MONGO_URI || 'mongodb://localhost:27017/pulse'
const client = new MongoClient(uri, { serverSelectionTimeoutMS: 5000 })
let db

async function connect() {
    await client.connect()
    db = client.db('sentience-mongoDB')
    console.log('✅ Connected to MongoDB')
}

function getDb() {
    return db
}

module.exports = { connect, getDb }