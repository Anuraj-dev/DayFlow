<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import PageHeader from '@/components/PageHeader.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, HttpError } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import type { EmployeeSummary } from '@/types/domain'

const route = useRoute()
const session = useSessionStore()
const person = ref<EmployeeSummary | null>(null)
const error = ref('')
const tab = ref('personal')

onMounted(async () => {
  try {
    person.value = await api(`/api/employees/${route.params.employeeId}`)
  } catch (err) {
    error.value = err instanceof HttpError ? err.detail : 'Could not load profile.'
  }
})
</script>

<template>
  <section class="sheet">
    <PageHeader
      :title="person ? `${person.first_name} ${person.last_name}` : 'Profile'"
      description="Personal, job, salary, and documents."
    />
    <p v-if="error" role="alert">{{ error }}</p>
    <Tabs v-else-if="person" v-model="tab">
      <TabsList>
        <TabsTrigger value="personal">Personal</TabsTrigger>
        <TabsTrigger value="job">Job</TabsTrigger>
        <TabsTrigger value="salary">Salary</TabsTrigger>
        <TabsTrigger value="documents">Documents</TabsTrigger>
      </TabsList>
      <TabsContent value="personal">
        <p>{{ person.email ?? 'Work email is on the employee record.' }}</p>
        <p>Employees can edit address, phone, and picture. HR can edit all fields.</p>
      </TabsContent>
      <TabsContent value="job">
        <p>{{ person.title ?? 'No title' }} · {{ person.department ?? 'No department' }}</p>
      </TabsContent>
      <TabsContent value="salary">
        <p>
          {{
            session.isHr
              ? 'Salary inputs stay here and in Payroll.'
              : 'Salary is read-only for employees.'
          }}
        </p>
      </TabsContent>
      <TabsContent value="documents">
        <p>Document upload is deferred. This tab stays visible so the surface is not silently omitted.</p>
      </TabsContent>
    </Tabs>
  </section>
</template>
