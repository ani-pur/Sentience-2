const { MongoClient } = require('mongodb')

const client = new MongoClient('mongodb://localhost:27017')
let db

async function connect() {
    await client.connect()
    db = client.db('pulse')
    console.log('✅ Connected to MongoDB')
}

function getDb() {
    return db
}

module.exports = { connect, getDb }