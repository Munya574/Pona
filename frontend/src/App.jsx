import { Routes, Route } from 'react-router-dom'
import Onboarding from './pages/Onboarding'
import Scan from './pages/Scan'
import Result from './pages/Result'
import Profile from './pages/Profile'
import ChefCard from './pages/ChefCard'
import BarcodeScan from './pages/BarcodeScan'

export default function App() {
  return (
    <div className="min-h-screen bg-white max-w-md mx-auto">
      <Routes>
        <Route path="/" element={<Onboarding />} />
        <Route path="/scan" element={<Scan />} />
        <Route path="/result" element={<Result />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/card" element={<ChefCard />} />
        <Route path="/barcode" element={<BarcodeScan />} />
      </Routes>
    </div>
  )
}
