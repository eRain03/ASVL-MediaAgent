import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import TasksPage from './pages/TasksPage'
import TaskDetailPage from './pages/TaskDetailPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
      </Routes>
    </Layout>
  )
}

export default App