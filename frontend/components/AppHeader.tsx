'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { supabase } from '@/lib/supabaseClient'

export default function AppHeader() {
  const router = useRouter()

  async function handleSignOut() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <header className="sticky top-0 z-10 flex min-h-14 flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border bg-background/80 px-6 py-3 backdrop-blur-md">
      <Link href="/dashboard" className="font-heading text-xs font-bold tracking-tight whitespace-nowrap text-primary sm:text-sm sm:tracking-wide">
        AI ENGINEERING PLATFORM
      </Link>
      <Button variant="ghost" size="sm" onClick={handleSignOut}>
        Sign out
      </Button>
    </header>
  )
}
