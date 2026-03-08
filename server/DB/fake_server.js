const { getDb } = require('../DB/mongo')

// Get all sentiment graph data for one brand
app.get('/api/sentiment', async (req, res) => {
    const db   = getDb()
    const brand = req.query.brand  // e.g. ?brand=google
    const data  = await db.collection('sentiment_graph')
                          .find({ brand })
                          .sort({ date: 1 })
                          .toArray()
    res.json(data)
})

// Get all available brands
app.get('/api/brands', async (req, res) => {
    const db     = getDb()
    const brands = await db.collection('sentiment_graph').distinct('brand')
    res.json(brands)
})

// Get raw posts for a brand
app.get('/api/posts', async (req, res) => {
    const db    = getDb()
    const brand = req.query.brand
    const posts = await db.collection(brand)
                          .find({ type: 'post' })
                          .sort({ created_utc: 1 })
                          .toArray()
    res.json(posts)
})

// Get daily sentiment buckets for a brand
app.get('/api/daily', async (req, res) => {
    const db    = getDb()
    const brand = req.query.brand
    const data  = await db.collection('daily_sentiment')
                          .find({ brand })
                          .sort({ date: 1 })
                          .toArray()
    res.json(data)
})