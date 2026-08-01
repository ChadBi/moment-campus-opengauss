$baseUrl = "http://localhost:8000/api/v1"
$schoolCode = "jiangnan"
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg1NDcwNTIwLCJpYXQiOjE3ODU0Mzk5MjAuNjE5NTgzLCJ0eXBlIjoiYWNjZXNzIn0.zvjTpQNIm3oA08Zt-bdIPlW0W5mg5Kj0P2L2WytTgtc"
$headers = @{
    "Authorization" = "Bearer $token"
    "X-School-Code" = $schoolCode
    "Content-Type" = "application/json"
}

$results = @()

function Test-Api {
    param($name, $method, $url, $body = $null)
    try {
        if ($method -eq "GET") {
            $resp = Invoke-RestMethod -Uri "$baseUrl$url" -Method GET -Headers $headers
        } else {
            $resp = Invoke-RestMethod -Uri "$baseUrl$url" -Method $method -Headers $headers -Body $body
        }
        return @{ name=$name; status="PASS"; data=$resp }
    } catch {
        return @{ name=$name; status="FAIL"; error=$_.Exception.Message }
    }
}

Write-Host "=== 此刻校园 API 全链路校验 ===" -ForegroundColor Cyan
Write-Host ""

# 1. listCategories
Write-Host "1. listCategories - 获取分类列表" -ForegroundColor Yellow
$r = Test-Api "listCategories" "GET" "/categories"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.Count) 个分类" }

# 2. listPosts (recommendations)
Write-Host "2. listPosts - 获取推荐列表" -ForegroundColor Yellow
$r = Test-Api "listPosts" "GET" "/recommendations?page=1&page_size=2"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.items.Count) 条推荐, total=$($r.data.total)" }

# 3. listTopics
Write-Host "3. listTopics - 获取话题列表" -ForegroundColor Yellow
$r = Test-Api "listTopics" "GET" "/topics?page=1&page_size=5"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.items.Count) 个话题" }

# 4. getHotTags
Write-Host "4. getHotTags - 获取热门标签" -ForegroundColor Yellow
$r = Test-Api "getHotTags" "GET" "/search/hot-tags"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.Count) 个标签" }

# 5. searchPosts
Write-Host "5. searchPosts - 关键词搜索" -ForegroundColor Yellow
$r = Test-Api "searchPosts" "GET" "/search?keyword=大学&page=1&page_size=3"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.items.Count) 条结果, total=$($r.data.total)" }

# 6. getPostDetail
Write-Host "6. getPostDetail - 获取帖子详情" -ForegroundColor Yellow
$r = Test-Api "getPostDetail" "GET" "/posts/30"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   帖子: $($r.data.post.title)" }

# 7. getMapMarkers
Write-Host "7. getMapMarkers - 获取地图标记" -ForegroundColor Yellow
$r = Test-Api "getMapMarkers" "GET" "/map/markers"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.markers.Count) 个标记" }

# 8. getMyPosts
Write-Host "8. getMyPosts - 获取我的此刻" -ForegroundColor Yellow
$r = Test-Api "getMyPosts" "GET" "/users/me/posts?page=1&page_size=5"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.items.Count) 条" }

# 9. getNotifications
Write-Host "9. getNotifications - 获取通知" -ForegroundColor Yellow
$r = Test-Api "getNotifications" "GET" "/notifications?page=1&page_size=5"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.items.Count) 条通知, 未读=$($r.data.unread_count)" }

# 10. getTopicDetail
Write-Host "10. getTopicDetail - 获取话题详情" -ForegroundColor Yellow
$r = Test-Api "getTopicDetail" "GET" "/topics/1"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   话题: $($r.data.topic.title)" }

# 11. likePost (toggle)
Write-Host "11. likePost - 点赞帖子" -ForegroundColor Yellow
$r = Test-Api "likePost" "POST" "/posts/30/like"
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   liked=$($r.data.liked), likes_count=$($r.data.likes_count)" }

# 12. createComment
Write-Host "12. createComment - 发表评论" -ForegroundColor Yellow
$commentBody = '{"content":"API全链路测试评论 - 校验通过","parent_id":null}'
$r = Test-Api "createComment" "POST" "/posts/30/comments" $commentBody
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   评论ID=$($r.data.id)" }

# 13. validatePost
Write-Host "13. validatePost - 协同验证" -ForegroundColor Yellow
$valBody = '{"validation_type":"confirmation"}'
$r = Test-Api "validatePost" "POST" "/posts/30/validations" $valBody
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   验证ID=$($r.data.id), type=$($r.data.validation_type)" }

# 14. aiSearch
Write-Host "14. aiSearch - AI语义搜索" -ForegroundColor Yellow
$aiBody = '{"query":"找一下自习室","page":1,"page_size":3}'
$r = Test-Api "aiSearch" "POST" "/search/ai" $aiBody
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   返回 $($r.data.items.Count) 条, intent=$($r.data.intent)" }

# 15. createPost
Write-Host "15. createPost - 发布此刻" -ForegroundColor Yellow
$postBody = '{"title":"API校验测试帖","content":"这是一条用于全链路校验的测试帖子","category_id":5,"location_name":"测试位置"}'
$r = Test-Api "createPost" "POST" "/posts" $postBody
$results += $r
Write-Host "   $($r.status)" -ForegroundColor $(if($r.status -eq "PASS"){"Green"}else{"Red"})
if ($r.data) { Write-Host "   新帖ID=$($r.data.id), status=$($r.data.status)" }

# Summary
Write-Host ""
Write-Host "=== 校验结果汇总 ===" -ForegroundColor Cyan
$passCount = ($results | Where-Object { $_.status -eq "PASS" }).Count
$failCount = ($results | Where-Object { $_.status -eq "FAIL" }).Count
Write-Host "总计: $($results.Count) 个 API"
Write-Host "通过: $passCount" -ForegroundColor Green
Write-Host "失败: $failCount" -ForegroundColor $(if($failCount -gt 0){"Red"}else{"Green"})

if ($failCount -gt 0) {
    Write-Host ""
    Write-Host "失败详情:" -ForegroundColor Red
    foreach ($r in $results | Where-Object { $_.status -eq "FAIL" }) {
        Write-Host "  $($r.name): $($r.error)"
    }
}
