'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import AuthForm from '@/components/AuthForm'

export default function SignupPage() {
  const router = useRouter()
  return (
    <main className="mx-auto flex w-full min-h-screen min-w-0 max-w-md flex-col justify-center px-6 py-16">
      <Link href="/" className="mb-8 font-heading text-sm font-bold tracking-wide text-primary">
        AI ENGINEERING PLATFORM
      </Link>
      <div className="punch-corner-lg card-stack-shadow border border-border bg-card p-8">
        <h1 className="font-heading text-2xl font-bold uppercase mb-6">Sign up</h1>
        <AuthForm mode="signup" onSuccess={() => router.push('/dashboard')} />
      </div>
      <p className="mt-6 text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link href="/login" className="text-foreground hover:text-primary">
          Log in
        </Link>
      </p>
    </main>
  )
}
