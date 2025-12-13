/* eslint-disable @typescript-eslint/explicit-function-return-type */
import { QueryConfig } from '@renderer/lib/react-query'
import { queryOptions, useQuery } from '@tanstack/react-query'

type TodoItemResponse = {
  userId: number
  id: number
  title: string
  completed: boolean
}

export const getTodos = async (): Promise<TodoItemResponse[]> => {
  const response = await window.api.todos.fetch()

  return response
}

export const getTodosQueryKey = (): string[] => ['todos']

export const getTodosQueryOptions = () => {
  return queryOptions({
    queryKey: getTodosQueryKey(),
    queryFn: getTodos
  })
}

type UseGetTodosParams = {
  queryConfig?: QueryConfig<typeof getTodosQueryOptions>
}

export const useGetTodos = (params: UseGetTodosParams = {}) => {
  return useQuery({
    ...getTodosQueryOptions(),
    ...params.queryConfig
  })
}
