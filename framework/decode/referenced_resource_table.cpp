/*
** Copyright (c) 2020 LunarG, Inc.
**
** Licensed under the Apache License, Version 2.0 (the "License");
** you may not use this file except in compliance with the License.
** You may obtain a copy of the License at
**
**     http://www.apache.org/licenses/LICENSE-2.0
**
** Unless required by applicable law or agreed to in writing, software
** distributed under the License is distributed on an "AS IS" BASIS,
** WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
** See the License for the specific language governing permissions and
** limitations under the License.
*/

#include "decode/referenced_resource_table.h"

#include <cassert>

GFXRECON_BEGIN_NAMESPACE(gfxrecon)
GFXRECON_BEGIN_NAMESPACE(decode)

void ReferencedResourceTable::AddResource(format::HandleId resource_id)
{
    if (resource_id != format::kNullHandleId)
    {
        resources_.emplace(resource_id, std::make_shared<ResourceInfo>());
    }
}

void ReferencedResourceTable::AddResource(format::HandleId parent_id, format::HandleId resource_id)
{
    if ((parent_id != format::kNullHandleId) && (resource_id != format::kNullHandleId))
    {
        auto parent_entry = resources_.find(parent_id);

        if (parent_entry != resources_.end())
        {
            auto& parent_info = parent_entry->second;
            assert(parent_info != nullptr);

            auto resource_entry = resources_.find(resource_id);
            if (resource_entry == resources_.end())
            {
                // The resource is not in the table, so add it to both the table and to the parent's child list.
                auto resource_info      = std::make_shared<ResourceInfo>();
                resource_info->is_child = true;

                parent_info->child_infos.emplace_back(std::weak_ptr<ResourceInfo>{ resource_info });
                resources_.emplace(resource_id, resource_info);
            }
            else
            {
                // The resource has already been added to the table, but has multiple parent objects (e.g. a framebuffer
                // is created from multiple image views), so we add it to the parent's child list.
                parent_info->child_infos.emplace_back(std::weak_ptr<ResourceInfo>{ resource_entry->second });
            }
        }
    }
}

void ReferencedResourceTable::AddResource(size_t                  parent_id_count,
                                          const format::HandleId* parent_ids,
                                          format::HandleId        resource_id)
{
    if ((parent_ids != nullptr) && (resource_id != format::kNullHandleId))
    {
        for (size_t i = 0; i < parent_id_count; ++i)
        {
            AddResource(parent_ids[i], resource_id);
        }
    }
}

void ReferencedResourceTable::AddResourceToContainer(format::HandleId container_id, format::HandleId resource_id)
{
    if ((container_id != format::kNullHandleId) && (resource_id != format::kNullHandleId))
    {
        auto container_entry = containers_.find(container_id);
        if (container_entry != containers_.end())
        {
            auto& container_info = container_entry->second;
            auto  resource_entry = resources_.find(resource_id);

            if (resource_entry != resources_.end())
            {
                auto& resource_info = resource_entry->second;
                assert((container_info != nullptr) && (resource_info != nullptr));

                container_info->resource_infos.emplace(resource_id, std::weak_ptr<ResourceInfo>{ resource_info });
            }
        }
    }
}

void ReferencedResourceTable::AddResourceToUser(format::HandleId user_id, format::HandleId resource_id)
{
    if ((user_id != format::kNullHandleId) && (resource_id != format::kNullHandleId))
    {
        auto user_entry = users_.find(user_id);
        if (user_entry != users_.end())
        {
            auto& user_info      = user_entry->second;
            auto  resource_entry = resources_.find(resource_id);

            if (resource_entry != resources_.end())
            {
                auto& resource_info = resource_entry->second;
                assert((user_info != nullptr) && (resource_info != nullptr));

                user_info->resource_infos.emplace(resource_id, std::weak_ptr<ResourceInfo>{ resource_info });
            }
        }
    }
}

void ReferencedResourceTable::AddContainerToUser(format::HandleId user_id, format::HandleId container_id)
{
    if ((user_id != format::kNullHandleId) && (container_id != format::kNullHandleId))
    {
        auto user_entry = users_.find(user_id);
        if (user_entry != users_.end())
        {
            auto& user_info       = user_entry->second;
            auto  container_entry = containers_.find(container_id);

            if (container_entry != containers_.end())
            {
                auto& container_info = container_entry->second;
                assert((user_info != nullptr) && (container_info != nullptr));

                user_info->container_infos.emplace(container_id,
                                                   std::weak_ptr<ResourceContainerInfo>{ container_info });
            }
        }
    }
}

void ReferencedResourceTable::AddUserToUser(format::HandleId user_id, format::HandleId source_user_id)
{
    if ((user_id != format::kNullHandleId) && (source_user_id != format::kNullHandleId))
    {
        auto user_entry = users_.find(user_id);
        if (user_entry != users_.end())
        {
            auto& user_info         = user_entry->second;
            auto  source_user_entry = users_.find(source_user_id);

            if (source_user_entry != users_.end())
            {
                auto& source_user_info = source_user_entry->second;
                assert((user_info != nullptr) && (source_user_info != nullptr));

                // Copy resource and container info from source user to destination user.
                auto&       resource_infos         = user_info->resource_infos;
                auto&       container_infos        = user_info->container_infos;
                const auto& source_resource_infos  = source_user_info->resource_infos;
                const auto& source_container_infos = source_user_info->container_infos;

                for (auto& source_resource_info : source_resource_infos)
                {
                    if (!source_resource_info.second.expired())
                    {
                        resource_infos.insert(source_resource_info);
                    }
                }

                for (auto& source_container_info : source_container_infos)
                {
                    if (!source_container_info.second.expired())
                    {
                        container_infos.insert(source_container_info);
                    }
                }
            }
        }
    }
}

void ReferencedResourceTable::AddContainer(format::HandleId pool_id, format::HandleId container_id)
{
    if ((pool_id != format::kNullHandleId) && (container_id != format::kNullHandleId))
    {
        auto container_info     = std::make_shared<ResourceContainerInfo>();
        container_info->pool_id = pool_id;
        containers_.emplace(container_id, std::move(container_info));
        container_pool_handles_[pool_id].insert(container_id);
    }
}

void ReferencedResourceTable::AddUser(format::HandleId pool_id, format::HandleId user_id)
{
    if ((pool_id != format::kNullHandleId) && (user_id != format::kNullHandleId))
    {
        auto user_info     = std::make_shared<ResourceUserInfo>();
        user_info->pool_id = pool_id;
        users_.emplace(user_id, std::move(user_info));
        user_pool_handles_[pool_id].insert(user_id);
    }
}

void ReferencedResourceTable::RemoveContainer(format::HandleId container_id)
{
    if (container_id != format::kNullHandleId)
    {
        auto container_entry = containers_.find(container_id);
        if (container_entry != containers_.end())
        {
            auto& container_info = container_entry->second;
            assert(container_info != nullptr);

            container_pool_handles_[container_info->pool_id].erase(container_id);
            containers_.erase(container_entry);
        }
    }
}

void ReferencedResourceTable::RemoveUser(format::HandleId user_id)
{
    if (user_id != format::kNullHandleId)
    {
        auto user_entry = users_.find(user_id);
        if (user_entry != users_.end())
        {
            auto& user_info = user_entry->second;
            assert(user_info != nullptr);

            user_pool_handles_[user_info->pool_id].erase(user_id);
            users_.erase(user_entry);
        }
    }
}

void ReferencedResourceTable::ResetContainer(format::HandleId container_id)
{
    if (container_id != format::kNullHandleId)
    {
        auto container_entry = containers_.find(container_id);
        if (container_entry != containers_.end())
        {
            auto& container_info = container_entry->second;
            assert(container_info != nullptr);

            container_info->resource_infos.clear();
        }
    }
}

void ReferencedResourceTable::ResetUser(format::HandleId user_id)
{
    if (user_id != format::kNullHandleId)
    {
        auto user_entry = users_.find(user_id);
        if (user_entry != users_.end())
        {
            auto& user_info = user_entry->second;
            assert(user_info != nullptr);

            user_info->resource_infos.clear();
            user_info->container_infos.clear();
        }
    }
}

void ReferencedResourceTable::ResetContainers(format::HandleId pool_id)
{
    if (pool_id != format::kNullHandleId)
    {
        auto& container_ids = container_pool_handles_[pool_id];
        for (auto container_id : container_ids)
        {
            ResetContainer(container_id);
        }
    }
}

void ReferencedResourceTable::ResetUsers(format::HandleId pool_id)
{
    if (pool_id != format::kNullHandleId)
    {
        auto& user_ids = user_pool_handles_[pool_id];
        for (auto user_id : user_ids)
        {
            ResetUser(user_id);
        }
    }
}

void ReferencedResourceTable::ClearContainers(format::HandleId pool_id)
{
    if (pool_id != format::kNullHandleId)
    {
        auto& container_ids = container_pool_handles_[pool_id];
        for (auto container_id : container_ids)
        {
            containers_.erase(container_id);
        }

        container_ids.clear();
    }
}

void ReferencedResourceTable::ClearUsers(format::HandleId pool_id)
{
    if (pool_id != format::kNullHandleId)
    {
        auto& user_ids = user_pool_handles_[pool_id];
        for (auto user_id : user_ids)
        {
            users_.erase(user_id);
        }

        user_ids.clear();
    }
}

void ReferencedResourceTable::ProcessUserSubmission(format::HandleId user_id)
{
    if (user_id != format::kNullHandleId)
    {
        auto user_entry = users_.find(user_id);
        if (user_entry != users_.end())
        {
            auto& user_info = user_entry->second;
            assert(user_info != nullptr);

            auto& resource_infos  = user_info->resource_infos;
            auto& container_infos = user_info->container_infos;

            for (auto& resource_info : resource_infos)
            {
                if (!resource_info.second.expired())
                {
                    auto resource_info_ptr  = resource_info.second.lock();
                    resource_info_ptr->used = true;
                }
            }

            for (auto& container_info : container_infos)
            {
                if (!container_info.second.expired())
                {
                    auto container_info_ptr = container_info.second.lock();
                    for (auto& resource_info : container_info_ptr->resource_infos)
                    {
                        if (!resource_info.second.expired())
                        {
                            auto resource_info_ptr  = resource_info.second.lock();
                            resource_info_ptr->used = true;
                        }
                    }
                }
            }
        }
    }
}

void ReferencedResourceTable::GetReferencedResourceIds(std::unordered_set<format::HandleId>* referenced_ids,
                                                       std::unordered_set<format::HandleId>* unreferenced_ids) const
{
    for (auto resource_entry : resources_)
    {
        auto& resource_info = resource_entry.second;

        if (!resource_info->is_child)
        {
            bool used = IsUsed(resource_info.get());

            if (used && (referenced_ids != nullptr))
            {
                referenced_ids->insert(resource_entry.first);
            }
            else if (!used && (unreferenced_ids != nullptr))
            {
                unreferenced_ids->insert(resource_entry.first);
            }
        }
    }
}

bool ReferencedResourceTable::IsUsed(const ResourceInfo* resource_info) const
{
    assert(resource_info != nullptr);

    if (resource_info->used)
    {
        return true;
    }
    else
    {
        // If the resource was not used directly, check to see if it was used indirectly through a child.
        for (const auto& child_info : resource_info->child_infos)
        {
            if (!child_info.expired())
            {
                const auto child_info_ptr = child_info.lock();
                if (IsUsed(child_info_ptr.get()))
                {
                    return true;
                }
            }
        }
    }

    return false;
}

GFXRECON_END_NAMESPACE(decode)
GFXRECON_END_NAMESPACE(gfxrecon)
