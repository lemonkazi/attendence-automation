import { useState } from 'react'
import axios from 'axios'

function App() {
  const [text, setText] = useState('')
  const [targetLang, setTargetLang] = useState('English')
  const [translation, setTranslation] = useState('')
  const [loading, setLoading] = useState(false)

  const handleTranslate = async () => {
    if (!text.trim()) {
      alert('Please enter some text first.')
      return
    }
    setLoading(true)
    try {
      const response = await axios.post('http://localhost:8502/translate', {
        text,
        target_lang: targetLang,
      })
      setTranslation(response.data.translation)
    } catch (error) {
      console.error('Translation error:', error)
      alert('Failed to translate. Check console for details.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1>🌍 Translator Agent</h1>
      <div>
        <label>Target Language: </label>
        <select value={targetLang} onChange={(e) => setTargetLang(e.target.value)}>
          <option value="English">English</option>
          <option value="Bengali">Bengali</option>
          <option value="Hindi">Hindi</option>
          <option value="Japanese">Japanese</option>
        </select>
      </div>
      <div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Enter text to translate"
          style={{ width: '100%', minHeight: '100px', margin: '1rem 0' }}
        />
      </div>
      <button onClick={handleTranslate} disabled={loading}>
        {loading ? 'Translating...' : 'Translate'}
      </button>
      {translation && (
        <div style={{ marginTop: '1rem', padding: '1rem', border: '1px solid #ccc', borderRadius: '4px' }}>
          <h3>Translation ({targetLang}):</h3>
          <p>{translation}</p>
        </div>
      )}
    </div>
  )
}

export default App
